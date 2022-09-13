# lift and shift starter + terraform migration assistant
## Summary

This repository is the starting point for lift and shift migration projects. It follows the 3 Musketeer pattern with centralized Terraform backend according to the [terraform-monorepo-starter](https://gitlab.mantelgroup.com.au/cmd/solution-accelerators/terraform-monorepo-starter) and includes the Terraform Migration Assistant.

The Terraform Migration Assistant generates Terraform code for EC2 instances by tag within a Terraform subfolder and workspace.

[Video Guide](https://conquer.cmd.com.au/mod/page/view.php?id=254)

## Table of Contents

- [Quick Start](#quick-start)
- [Templates](#templates)
  - [Templates variables](#templates-variables)
- [Accomodating the Terraform Migration Assistant in an ongoing project](#accomodating-terraform-migration-assistant-in-an-ongoing-project)
  - [docker-compose.yml](#docker-composeyml)
  - [Makefile](#makefile)
  - [envvars.yml](#envvarsyml)
- [Terraform Migration Assistant Container](#terraform-migration-assistant-container)
## Quick Start

- Ensure you have a Terraform S3 backend with DynamoDB already deployed in the shared account. If you need to deploy it follow the instructions from [terraform-monorepo-starter](https://gitlab.mantelgroup.com.au/cmd/solution-accelerators/terraform-monorepo-starter)
- Copy the contents from this repo (remember to ignore the .git folder) into your new repository
- Configure the Terraform backend on the `Makefile`,  filling up the variable values below:

````Makefile
# Backend Configuration
BACKEND_BUCKET = 
BACKEND_KEY = 
BACKEND_REGION = 
BACKEND_PROFILE = 
BACKEND_DYNAMODB_TABLE = 
````

- Set the desired Terraform version on `Makefile`, changing the `TERRAFORM_VERSION` variable value. Tip, for new projects, start using the latest version available and keep it unless the project has a specific requirement.

````Makefile
# Terraform Version
export TERRAFORM_VERSION = 1.0.10
````

- In AWS console or during the migration, apply a common tag key and tag value to the instance(s) you are going to generate Terraform code
- Ensure all instances have a tag `Name` with a valid value without spaces. This tag will be the `<instance tag Name value>.tf` Terraform file.
- Ensure you have the AWS profile configured and you are authenticated for both backend (shared services account) and the tagged EC2 instances AWS accounts
- Run the following command, replacing the variable values accordingly:

````bash
TERRAFORM_ROOT_MODULE=<desired or existing subfolder name> TERRAFORM_WORKSPACE=<desired or existing Terraform workspace> TFMA_TAG_KEY=<Tag Key> TFMA_TAG_VALUE=<Tag Value> AWS_PROFILE=<AWS Profile name> AWS_DEFAULT_REGION=<region where the instance(s) lives> make tfimport
````

- Command example:

````bash
TERRAFORM_ROOT_MODULE=staging TERRAFORM_WORKSPACE=staging TFMA_TAG_KEY=AWSApplicationMigrationServiceSourceServerID TFMA_TAG_VALUE=s-9d88fd5d9786c7326 AWS_PROFILE=default AWS_DEFAULT_REGION=ap-southeast-1 make tfimport
````

- It creates Terraform subfolder and/or workspace if needed, or use the existing
- It never overwrites the existing Terraform files and backend resources unless you use the optional variable `TFMA_OVERWRITE_EXISTING=True`
- You can enable debug with the optional variable `TFMA_DEBUG=True`
- Now, run a Terraform plan:
  
```` bash
TERRAFORM_ROOT_MODULE=staging TERRAFORM_WORKSPACE=staging make plan
````

- Review the plan output. Make sure that `aws_instance` resource is not going to be destroyed as the servers are pets, change everything you need, for instance, add Security Groups, tags, etc... Run a new Terraform plan, when you are happy with the results proceed to the next step
- Apply the changes:

```` bash
TERRAFORM_ROOT_MODULE=<subfolder name> TERRAFORM_WORKSPACE=<workspace> make apply
````

## Templates

The Terraform Migration Assistant uses [Jinja2](https://jinja2docs.readthedocs.io/en/stable/) templates, which allows customizing the Terraform imported code.

- The templates are located in the `_templates` folder.
- Templates should have additional `.j2` extension, as `terraform.tf.j2`, `locals.tf.j2`, `data.tf` or `.gitlab-ci.yml.j2`
- `_instance.tf.j2` is a special template generating a `<instance tag Name value>.tf` file, one file for each imported instance in the group.
- All other templates will be generated once.
- You can generate Terraform, Gitlab CI, or even README.md files.
- Because the migrated instances are pet, this repository pattern is slightly different from our standard. The `<instance name>.tf` files popup with all parameters. Use `locals.tf` to define common variables.

### Templates variables

[Jinja2](https://jinja2docs.readthedocs.io/en/stable/) replaces variables between double curly brackets as `{{ variable }}`, also support [loops and conditionals](https://ttl255.com/jinja2-tutorial-part-2-loops-and-conditionals/).

For all files the available variables are:

- `base_dir` value from TERRAFORM_ROOT_MODULE
- `tf_workspace` value from TERRAFORM_WORKSPACE
- `aws_profile` value from AWS_PROFILE
- `aws_default_region` value from AWS_DEFAULT_REGION

In addition to the variables above, `_instances.tf` has the following variables available:

- `instance_name` instance name from the instance tag Name
- `metadata.instance_type` instance type/size
- `metadata.ami_id` instance AMI ID
- `metadata.vpc_id`: VPC ID where the instance lives
- `metadata.subnet_id` Subnet ID where the instance lives
- `root_volume.type` Root volume type
- `root_volume.size` Root volume size
- `root_volume.encrypted` Root volume encrypted
- `root_volume.iops` Root volume IOPS
- `root_volume.kms_key_id` Root volume KMS Key ID
- `volume.type` EBS volume type
- `volume.size` EBS volume size
- `volume.encrypted` EBS volume encrypted
- `volume.iops` EBS volume IOPS
- `volume.kms_key_id` EBS volume KMS Key ID

Also, more variables can be included editing the Terraform Migration Assistant Python code located in `_terraform-migration-assistant\terraform-migration-assistant.py` 

## Accomodating the Terraform Migration Assistant in an ongoing project

An ongoing project may follow a slightly different pattern in its repository. For accomodating Terraform Migration Assistant in your existing project, you need to match the templates, copy the folders `_terraform-migration-assistant` and  `_templates` into your repository and edit your `docker-compose.yml`, `Makefile`, and `envvars.yml` as explained below.

### docker-compose.yml

Edit your current `terraform-utils` service to use the official Terraform image with the `${TERRAFORM_VERSION}` variable as the container tag:  `hashicorp/terraform:${TERRAFORM_VERSION}`

````yaml
  terraform-utils:
    image: hashicorp/terraform:${TERRAFORM_VERSION}
    env_file: .env
    environment:
      - AWS_SDK_LOAD_CONFIG=1
    entrypoint: ""
    volumes:
      - .:/work
      - ~/.aws:/root/.aws
    working_dir: /work
````

Add the terraform-migration-assistant service

````yaml
  terraform-migration-assistant:
    build: _terraform-migration-assistant
    env_file: .env
    volumes:
      - .:/work
      - ./_templates:/terraform-migration-assistant/_templates
      - ~/.aws:/root/.aws
````

Ensure you have an envvars service

````yaml
  envvars:
    image: flemay/envvars:0.0.7
    env_file: .env
    working_dir: /work
    volumes:
      - .:/work
````

### Makefile

Add the TERRAFORM_VERSION variable, matching with the current Terraform version used in the project.

````Makefile
# Terraform Version
export TERRAFORM_VERSION = 1.0.10
````

Add the Terraform Migration Assistant block, change the variable names in your `Makefile` if required to match with the Terraform Migration Assistant variable pattern.

````Makefile
## Terraform Migration Assistant

## Generate code and import for existing EC2 instance(s)
tfimport: .env _build
	docker-compose run --rm envvars ensure --tags terraform-migration-assistant
	docker-compose run --rm terraform-migration-assistant
.PHONY: tfimport

## Initialise Terraform from inside the Terraform Migration Assistant container
_init:
	cd $(TERRAFORM_ROOT_MODULE); terraform init $(BACKEND_CONFIG)
.PHONY: init

## Switch to specified workspace from inside the Terraform Migration Assistant container
_workspace:
	cd $(TERRAFORM_ROOT_MODULE); terraform workspace select $(TERRAFORM_WORKSPACE) || terraform workspace new $(TERRAFORM_WORKSPACE)
.PHONY: workspace

## Format generated Terraform code from inside the Terraform Migration Assistant container
	terraform fmt -diff -recursive
.PHONY: _format

## Build the Terraform Migration Assistant container
_build:
	docker-compose build --build-arg TERRAFORM_VERSION=${TERRAFORM_VERSION}
PHONY: _build
````

### envvars.yml

Add the required envvars and tags to envvars.yml, you may need to change your variable names to match with the Terraform Migration Assistant variable definition

````yaml
envvars:
  - name: TERRAFORM_WORKSPACE
    desc: Terraform Workspace that will be deployed to
    tags:
      - terraform
      - terraform-migration-assistant

  - name: TERRAFORM_ROOT_MODULE
    desc: Terraform Root Module (Directory) to deploy
    tags:
      - terraform
      - terraform-init
      - terraform-migration-assistant

  - name: TFMA_TAG_KEY
    desc: Instance(s) tag key
    tags:
      - terraform-migration-assistant

  - name: TFMA_TAG_VALUE
    desc: Instance(s) tag value
    tags:
      - terraform-migration-assistant

  - name: AWS_PROFILE
    desc: AWS profile to use for assuming role
    tags:
      - terraform-migration-assistant      

  - name: TFMA_DEBUG
    desc: Enable debug logging"
    optional: true
    tags:
      - terraform-migration-assistant

  - name: TFMA_OVERWRITE_EXISTING
    desc: Overwrite existing files and resources already present in the terraform state file
    optional: true
    tags:
      - terraform-migration-assistant

  - name: AWS_DEFAULT_REGION
    desc: AWS Region
    optional: true
    tags:
      - terraform-migration-assistant

tags:
  - name: terraform
    desc: Required to run Terraform commands
  - name: terraform-init
    desc: Required to run Terraform init
  - name: terraform-migration-assistant
    desc: Required to run Terraform Migration Assistant
````

## Terraform Migration Assistant Container

The Terraform Migration Assistant Container is created locally on your computer in the first run. When Terraform version or the source code is changed the container is updated automatically. At the end of the project you can delete the container with regular docker commands. `docker image ls` to list the images and `docker image rm <image name or ID>` to delete the image.

## Removing the Terraform Migration Assistant

You may need to remove the Terraform Migration Assistant from your repository, just use the instructions below:

- Delete the folders `_terraform-migration-assistant`, and `_templates`.
- Remove the service `terraform-migration-assistant` in `docker-compose.yml`
- Hardcode the Terraform version to `docker-compose.yml` replacing `${TERRAFORM_VERSION}`
- Remove `TERRAFORM_VERSION` variable and `Terraform Migration Assistant` targets in `Makefile`
- Remove the `envvars` and `tags` related to the `Terraform Migration Assistant` from `envvars.yml`
