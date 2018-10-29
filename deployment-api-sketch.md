### `POST /v1/deployments/` - Create a new deployment

#### Example request body:

```json
{
    "node_uuid": "878c3113-0035-5033-9f99-46520b89b56d",
    "instance_info": {
        "configdrive": {
            "hostname":"my-ubuntu-server"
        },
        "image_source": "https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img",
        "image_type": "wholedisk",
        "image_format": "qcow2"
    }
}
```

#### Example response body:

```json
{
    "uuid": "a597d2e9-596b-48e7-b346-2d03ff511bb4",
    "node_uuid": "878c3113-0035-5033-9f99-46520b89b56d",
    "info": {
        "configdrive": "*****",
        "image_source": "https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img",
        "image_type": "wholedisk",
        "image_format": "qcow2",
        "image_checksum": "1273tjhbsdasd2"
    }
}
```

### `GET /v1/deployments` - List all existing deployments

#### Example response body

```json
{
    "deployments": [
        {
            "uuid": "a597d2e9-596b-48e7-b346-2d03ff511bb4",
            "node_uuid": "878c3113-0035-5033-9f99-46520b89b56d",
            "info": {
                "configdrive": "*****",
                "image_source": "https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img",
                "image_type": "wholedisk",
                "image_format": "qcow2",
                "image_checksum": "1273tjhbsdasd2"
            }
        },
        {
            "uuid": "06683d14-2117-487e-b103-4a2bebd570da",
            "node_uuid": "d3f62783-97e2-4e8e-9517-00e974a16aaf",
            "info": {
                "configdrive": "*****",
                "image_source": "https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img",
                "image_type": "wholedisk",
                "image_format": "qcow2",
                "image_checksum": "1273tjhbsdasd2"
            }
        }
    ]
}
```

### `GET /v1/deployments/<deployment UUID>` - Get info about a specific deployment

#### Example response body

```json
{
    "uuid": "a597d2e9-596b-48e7-b346-2d03ff511bb4",
    "node_uuid": "878c3113-0035-5033-9f99-46520b89b56d",
    "info": {
        "configdrive": "*****",
        "image_source": "https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img",
        "image_type": "wholedisk",
        "image_format": "qcow2",
        "image_checksum": "1273tjhbsdasd2"
    }
}
```

### `DELETE /v1/deployments/<deployment UUID>` - Delete a deployment

### `POST /v1/deployments/<deployment UUID>` - Rebuild a deployment

#### Example request body

```json
{
    "instance_info": {
        "configdrive": {
            "hostname":"my-ubuntu-server"
        },
        "image_source": "https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img",
        "image_type": "wholedisk",
        "image_format": "qcow2"
    }
}
```

#### Example response body

```json
{
    "uuid": "a597d2e9-596b-48e7-b346-2d03ff511bb4",
    "node_uuid": "878c3113-0035-5033-9f99-46520b89b56d",
    "info": {
        "configdrive": "*****",
        "image_source": "https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img",
        "image_type": "wholedisk",
        "image_format": "qcow2",
        "image_checksum": "1273tjhbsdasd2"
    }
}
```
