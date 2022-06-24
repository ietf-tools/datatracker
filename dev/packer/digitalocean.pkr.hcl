variable "do_api_token" {
  type      = string
  default   = "${env("DIGITALOCEAN_API_TOKEN")}"
  sensitive = true
}

variable "do_region" {
  type      = string
  default   = "tor1"
}

variable "do_size" {
  type      = string
  default   = "s-4vcpu-8gb"
}

# "timestamp" template function replacement
locals { timestamp = regex_replace(timestamp(), "[- TZ:]", "") }

# All locals variables are generated from variables that uses expressions
# that are not allowed in HCL2 variables.
# Read the documentation for locals blocks here:
# https://www.packer.io/docs/templates/hcl_templates/blocks/locals
locals {
  image_name = "datatracker-snapshot-${local.timestamp}"
}

# source blocks are generated from your builders; a source can be referenced in
# build blocks. A build block runs provisioner and post-processors on a
# source. Read the documentation for source blocks here:
# https://www.packer.io/docs/templates/hcl_templates/blocks/source
source "digitalocean" "do_source" {
  api_token     = "${var.do_api_token}"
  image         = "ubuntu-22-04-x64"
  region        = "${var.do_region}"
  size          = "${var.do_size}"
  snapshot_name = "${local.image_name}"
  ssh_username  = "root"
}

# a build block invokes sources and runs provisioning steps on them. The
# documentation for build blocks can be found here:
# https://www.packer.io/docs/templates/hcl_templates/blocks/build
build {
  sources = ["source.digitalocean.do_source"]

  provisioner "shell" {
    inline = ["cloud-init status --wait"]
  }

  provisioner "file" {
    destination = "/var/lib/cloud/scripts/per-instance/001-onboot.sh"
    source = "scripts/001-onboot.sh"
  }

  provisioner "file" {
    destination = "/rsync-assets.sh"
    source = "../../docker/scripts/app-rsync-extras.sh"
  }

  provisioner "shell" {
    inline = [
      "chmod +x /var/lib/cloud/scripts/per-instance/001-onboot.sh",
      "chmod +x /rsync-assets.sh"
    ]
  }

  provisioner "shell" {
    environment_vars = [
      "DEBIAN_FRONTEND=noninteractive",
      "LC_ALL=C",
      "LANG=en_US.UTF-8",
      "LC_CTYPE=en_US.UTF-8"
    ]
    inline = [
      "apt -qqy update",
      "apt -qqy -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold' full-upgrade",
      "apt -qqy -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold' install apt-transport-https ca-certificates curl jq linux-image-extra-virtual software-properties-common gnupg-agent openssl",
      "apt-get -qqy clean"
    ]
  }

  provisioner "shell" {
    environment_vars = [
      "DEBIAN_FRONTEND=noninteractive",
      "LC_ALL=C",
      "LANG=en_US.UTF-8",
      "LC_CTYPE=en_US.UTF-8"
    ]
    scripts = [
      "scripts/010-app.sh",
      "scripts/012-grub-opts.sh",
      "scripts/013-docker-dns.sh",
      "scripts/014-ufw-docker.sh",
      "scripts/900-cleanup.sh"
    ]
  }

}
