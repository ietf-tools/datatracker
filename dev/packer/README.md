# Packer Configuration
##### Automated cloud compute instance provisioning

## Installation

- Install the [Packer CLI](https://www.packer.io/downloads) on your machine.

## Usage

Use the `packer build` command with the builder of your choice. You must provide the required variables for the selected builder *(see below)*.

For example, provisioning on DigitalOcean would require the `do_api_token` to be provided with a valid DigitalOcean API Token:

```sh
packer build -var do_api_token=XYZ digitalocean.pkr.hcl
```

## Builders

### DigitalOcean

| Variable       | Description            | Required | Default       |
|----------------|------------------------|:--------:|---------------|
| `do_api_token` | DigitalOcean API Token |     Y    |               |
| `do_region`    | Region to build ot     |     N    | `tor1`        |
| `do_size`      | Droplet size to use    |     N    | `s-4vcpu-8gb` |

> Note: See https://slugs.do-api.dev for all possible slugs for droplet sizes and regions.
