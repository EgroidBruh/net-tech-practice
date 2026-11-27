#!/bin/sh
set -eu
: "${ESL_PASSWORD:=local-esl-password}"
: "${SIP_PASSWORD:=local-sip-password}"
: "${SIP_DOMAIN:=localhost}"
: "${FREESWITCH_EXTERNAL_IP:=127.0.0.1}"
# Values become XML attributes and sed replacements; disallow metacharacters.
for value in "$ESL_PASSWORD" "$SIP_PASSWORD" "$SIP_DOMAIN" "$FREESWITCH_EXTERNAL_IP"; do
  case "$value" in
    ''|*[!A-Za-z0-9_.-]*) echo 'Invalid FreeSWITCH environment value' >&2; exit 1 ;;
  esac
done
mkdir -p /etc/freeswitch /var/log/freeswitch /var/lib/freeswitch/db
mkdir -p /etc/freeswitch/directory
cp /opt/duty/conf/freeswitch.xml /opt/duty/conf/vars.xml /etc/freeswitch/
cp /opt/duty/conf/directory/default.xml /etc/freeswitch/directory/
for directory in autoload_configs sip_profiles dialplan; do
  cp -R "/opt/duty/conf/$directory" /etc/freeswitch/
done
for file in /etc/freeswitch/vars.xml /etc/freeswitch/autoload_configs/*.xml /etc/freeswitch/sip_profiles/*.xml; do
  sed -i -e "s/__ESL_PASSWORD__/$ESL_PASSWORD/g" -e "s/__SIP_PASSWORD__/$SIP_PASSWORD/g" -e "s/__SIP_DOMAIN__/$SIP_DOMAIN/g" -e "s/__EXTERNAL_IP__/$FREESWITCH_EXTERNAL_IP/g" "$file"
done
exec /usr/bin/freeswitch -nf -nonat -conf /etc/freeswitch -log /var/log/freeswitch -db /var/lib/freeswitch/db
