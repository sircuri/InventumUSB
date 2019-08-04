set -ex

# SET THE FOLLOWING VARIABLES

# MQTT_Port
# MQTT_Server
# MQTT_Topic
# MQTT_ClientId
# Inventum_LogFile
# Inventum_LogLevel
# SSH_PRIVATE_KEY

BASEVERSION="$(date +'%Y.%m')"
VERSION="${BASEVERSION}.${CI_PIPELINE_ID}"
if [ $CI_COMMIT_REF_SLUG != "master" ]; then
    VERSION="${VERSION}-B${CI_COMMIT_REF_SLUG}"
fi

IMAGE=InventumUSB
package="${IMAGE}.${VERSION}.tar.gz"

# Setup OpenSSH agent
apk add --update openssh-client
apk add --update libintl
apk add --virtual build_deps gettext
cp /usr/bin/envsubst /usr/local/bin/envsubst
apk del build_deps

eval $(ssh-agent -s)

echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add - > /dev/null

mkdir -p ~/.ssh
chmod 700 ~/.ssh

# extract config file from package
cd out
tar -xvzf $package ./etc/inventumusb.conf

envsubst < "etc/inventumusb.conf" > "etc/inventumusb.conf.replaced"
cat etc/inventumusb.conf.replaced

ssh -o StrictHostKeyChecking=no pi@$TARGET_IP "mkdir -p ~/.deploy/${VERSION}"
scp $package pi@$TARGET_IP:~/.deploy/${VERSION}/${IMAGE}.tar.gz
scp etc/inventumusb.conf.replaced pi@$TARGET_IP:~/.deploy/${VERSION}/inventumusb.conf.replaced

ssh pi@$TARGET_IP "cd ~/.deploy/${VERSION} && tar -xvzf InventumUSB.tar.gz && rm InventumUSB.tar.gz && /bin/sh ./deploy/stop-services.sh && /bin/sh ./deploy/install-dependencies.sh && /bin/sh ./deploy/setup-application.sh && /bin/sh ./deploy/setup-restartd.sh"
