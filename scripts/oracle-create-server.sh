#!/usr/bin/env bash
# Creates the free Oracle Cloud server for Sharp-Eyes, retrying "Out of
# capacity" until a server frees up. Run it in Oracle Cloud Shell, which is
# already signed in. Safe to run again: it reuses the network and stops if the
# server already exists. See docs/deploy-oracle-free.md.
#
# Settings (optional, as environment variables):
#   OCPUS=2 MEMORY_GB=12   server size (Always Free allows 2 OCPUs / 12 GB in total)
#   DISK_GB=200            boot disk (Always Free allows 200 GB in total)
#   WAIT_SECONDS=90        pause between attempts
set -uo pipefail

OCPUS=${OCPUS:-2}
MEMORY_GB=${MEMORY_GB:-12}
DISK_GB=${DISK_GB:-200}
WAIT_SECONDS=${WAIT_SECONDS:-90}
NAME=sharp-eyes
SHAPE=VM.Standard.A1.Flex
KEY_FILE="$HOME/.ssh/id_rsa.pub"

say() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { say "STOPPED: $*"; exit 1; }

COMPARTMENT=${OCI_TENANCY:-}
[ -n "$COMPARTMENT" ] || die "run this in Oracle Cloud Shell (OCI_TENANCY is not set)."
[ -f "$KEY_FILE" ] || die "no SSH key at $KEY_FILE. Run: ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N \"\""

existing=$(oci compute instance list --compartment-id "$COMPARTMENT" --display-name "$NAME" --all \
  | jq -r '.data[]? | select(."lifecycle-state" != "TERMINATED" and ."lifecycle-state" != "TERMINATING") | .id' | head -n1)
if [ -n "$existing" ]; then
  ip=$(oci compute instance list-vnics --instance-id "$existing" | jq -r '.data[0]."public-ip" // empty')
  say "A server named $NAME already exists. Public IP: ${ip:-unknown}"
  exit 0
fi

# Network: reuse the first public subnet, otherwise build one (VCN, internet
# gateway, default route). The default security list allows SSH only.
subnet=$(oci network subnet list --compartment-id "$COMPARTMENT" --all \
  | jq -r '[.data[]? | select(."prohibit-public-ip-on-vnic" == false and ."lifecycle-state" == "AVAILABLE")][0].id // empty')
if [ -z "$subnet" ]; then
  say "Creating the network..."
  vcn=$(oci network vcn create --compartment-id "$COMPARTMENT" --cidr-block 10.0.0.0/16 \
    --display-name "$NAME-vcn" --dns-label sharpeyes --wait-for-state AVAILABLE | jq -r '.data.id') \
    || die "could not create the network."
  route_table=$(oci network vcn get --vcn-id "$vcn" | jq -r '.data."default-route-table-id"')
  gateway=$(oci network internet-gateway create --compartment-id "$COMPARTMENT" --vcn-id "$vcn" \
    --is-enabled true --display-name "$NAME-gateway" --wait-for-state AVAILABLE | jq -r '.data.id') \
    || die "could not create the internet gateway."
  oci network route-table update --rt-id "$route_table" --force \
    --route-rules "[{\"destination\":\"0.0.0.0/0\",\"destinationType\":\"CIDR_BLOCK\",\"networkEntityId\":\"$gateway\"}]" \
    >/dev/null || die "could not add the internet route."
  subnet=$(oci network subnet create --compartment-id "$COMPARTMENT" --vcn-id "$vcn" \
    --cidr-block 10.0.0.0/24 --display-name "$NAME-subnet" --dns-label public \
    --wait-for-state AVAILABLE | jq -r '.data.id') || die "could not create the subnet."
fi
say "Network ready."

image=$(oci compute image list --compartment-id "$COMPARTMENT" --operating-system "Canonical Ubuntu" \
  --operating-system-version "24.04" --shape "$SHAPE" --sort-by TIMECREATED --sort-order DESC --limit 1 \
  | jq -r '.data[0].id // empty')
[ -n "$image" ] || die "could not find the Ubuntu 24.04 image for $SHAPE."

mapfile -t zones < <(oci iam availability-domain list --compartment-id "$COMPARTMENT" | jq -r '.data[].name')
[ "${#zones[@]}" -gt 0 ] || die "could not list availability domains."
say "Asking for $OCPUS OCPUs / $MEMORY_GB GB / $DISK_GB GB disk in ${#zones[@]} zone(s). Leave this tab open."

attempt=0
while true; do
  for zone in "${zones[@]}"; do
    attempt=$((attempt + 1))
    if out=$(oci compute instance launch --compartment-id "$COMPARTMENT" --availability-domain "$zone" \
        --display-name "$NAME" --shape "$SHAPE" \
        --shape-config "{\"ocpus\":$OCPUS,\"memoryInGBs\":$MEMORY_GB}" \
        --image-id "$image" --subnet-id "$subnet" --assign-public-ip true \
        --boot-volume-size-in-gbs "$DISK_GB" --ssh-authorized-keys-file "$KEY_FILE" \
        --wait-for-state RUNNING 2>&1); then
      id=$(printf '%s' "$out" | sed -n '/^{/,$p' | jq -r '.data.id')
      ip=$(oci compute instance list-vnics --instance-id "$id" | jq -r '.data[0]."public-ip" // empty')
      say "Got it! Server is running. Public IP: $ip"
      say "Next: ssh ubuntu@$ip"
      exit 0
    fi
    case "$out" in
      *[Cc]apacity*) say "Attempt $attempt ($zone): out of capacity." ;;
      *TooManyRequests*) say "Attempt $attempt: Oracle asked to slow down."; sleep "$WAIT_SECONDS" ;;
      *LimitExceeded*) printf '%s\n' "$out"
        die "over the free limit. Check that no other ARM server exists, or lower OCPUS and MEMORY_GB." ;;
      *) printf '%s\n' "$out"; die "unexpected error (above). Paste it to Claude." ;;
    esac
  done
  sleep "$WAIT_SECONDS"
done
