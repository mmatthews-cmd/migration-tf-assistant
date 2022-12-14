#!/usr/bin/env make
include Makehelp

# Terraform Version
export TERRAFORM_VERSION = 1.0.10

# Backend Configuration
BACKEND_BUCKET = aws-specific-bucket-name-terraform-backend
BACKEND_KEY = give-a-name-for-this
BACKEND_REGION = us-east-1
BACKEND_PROFILE = default
BACKEND_DYNAMODB_TABLE = aws-specific-dynamodb-name-terraform-lock

BACKEND_CONFIG = -backend-config="bucket=${BACKEND_BUCKET}" -backend-config="key=${BACKEND_KEY}/${TERRAFORM_ROOT_MODULE}" -backend-config="region=${BACKEND_REGION}" -backend-config="profile=${BACKEND_PROFILE}" -backend-config="dynamodb_table=${BACKEND_DYNAMODB_TABLE}" -backend-config="encrypt=true"

## Initialise Terraform
init: .env
	docker-compose run --rm envvars ensure --tags terraform-init
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform init ${BACKEND_CONFIG}'
.PHONY: init

## Initialise Terraform but also upgrade modules/providers
upgrade: .env init
	docker-compose run --rm envvars ensure --tags terraform-init
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform init -upgrade ${BACKEND_CONFIG}'
.PHONY: upgrade

## Generate a plan
plan: .env init workspace
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform plan'
.PHONY: plan

## Generate a plan and save it to the root of the repository. This should be used by CICD systems
planAuto: .env init workspace
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform plan -out ../${TERRAFORM_ROOT_MODULE}-${TERRAFORM_WORKSPACE}.tfplan'
.PHONY: planAuto

## Generate a plan and apply it
apply: .env init workspace
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform apply'
.PHONY: apply

## Apply the plan generated by planAuto. This should be used by CICD systems
applyAuto: .env init workspace
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform apply -auto-approve ../${TERRAFORM_ROOT_MODULE}-${TERRAFORM_WORKSPACE}.tfplan'
.PHONY: applyAuto

## Destroy resources
destroy: .env init workspace
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform destroy'
.PHONY: destroy

## Show the statefile
show: .env init workspace
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform show'
.PHONY: show

## Show root module outputs
output: .env init workspace
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform output'
.PHONY: output

## Switch to specified workspace
workspace: .env
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd $(TERRAFORM_ROOT_MODULE); terraform workspace select $(TERRAFORM_WORKSPACE) || terraform workspace new $(TERRAFORM_WORKSPACE)'
.PHONY: workspace

## Validate terraform is syntactically correct
validate: .env init
	docker-compose run --rm envvars ensure --tags terraform
	docker-compose run --rm terraform-utils sh -c 'cd ${TERRAFORM_ROOT_MODULE}; terraform validate'
.PHONY: validate

## Format all Terraform files
format: .env
	docker-compose run --rm terraform-utils terraform fmt -diff -recursive
.PHONY: format

## Interacticely launch a shell in the Terraform docker container
shell: .env
	docker-compose run --rm terraform-utils sh
.PHONY: shell

## Generate Docker env file
.env:
	touch .env
	docker-compose run --rm envvars validate
	docker-compose run --rm envvars envfile --overwrite
.PHONY: .env

## Terraform Migration Assistant

## Generate code and import for existing EC2 instance(s)
tfimport: .env _build
	docker-compose run --rm envvars ensure --tags terraform-migration-assistant
	docker-compose run --rm terraform-migration-assistant
.PHONY: tfimport

## Initialise Terraform from inside the Terraform Migration Assistant container
_init:
	pwd
	ls
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
