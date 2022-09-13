import boto3
import click
import jinja2
import logging
import os
import sh
import sys

from pprint import pprint
from sh import terraform  # pylint: disable=no-name-in-module
from sh import make

logger = logging.getLogger(__name__)

def list_instances_by_tag_value(tagkey, tagvalue):

    ec2client = boto3.client('ec2')

    response = ec2client.describe_instances(
        Filters=[
            {
                'Name': 'tag:'+tagkey,
                'Values': [tagvalue]
            }
        ]
    )
    instancelist = []
    for reservation in (response["Reservations"]):
        for instance in reservation["Instances"]:
            instancelist.append(instance["InstanceId"])
    return instancelist

def get_ec2_info(instance_id):
    ec2_client = boto3.client('ec2')
    ec2 = boto3.resource("ec2")
    instance = ec2.Instance(instance_id)
    for i in instance.tags:
        if i.get("Key") == "Name":
            instance_name = i.get("Value")

    #Identify attached Security Groups and store the SG IDs as String
    security_groups = instance.security_groups
    security_groups_id_list_as_string = ""
    for item in security_groups:
        security_group_id = item["GroupId"]
        security_groups_id_list_as_string = security_groups_id_list_as_string + '"' + security_group_id + '"' + ','
    security_groups_id_list_as_string = security_groups_id_list_as_string[:-1]

    #identify instance tags
    instance_tags = instance.tags
    instance_tags_as_string = ''
    tags_exclusion_keys = ['aws:ec2launchtemplate:id', 'aws:ec2launchtemplate:version']
    for tag in instance_tags:
        if tag['Key'] not in tags_exclusion_keys:
            tag_string = '"' + tag['Key'] + '"' + ' = ' + '"' + tag['Value'] + '"' + '\n\t\t'
            instance_tags_as_string = instance_tags_as_string + tag_string

    # Identify user data
    try:
        UserData = ec2_client.describe_instance_attribute(Attribute='userData', InstanceId=instance_id)['UserData']['Value']
    except:
        UserData = ""
    
    ebsOptimized = str(ec2_client.describe_instance_attribute(Attribute='ebsOptimized', InstanceId=instance_id)['EbsOptimized']['Value']).lower()
    print('ebsOptimized', ebsOptimized)

    metadata = {
        "instance_type": instance.instance_type,
        "ami_id": instance.image_id,
        "vpc_id": instance.vpc_id,
        "subnet_id": instance.subnet_id,
        "iam_instance_profile": instance.iam_instance_profile['Arn'].split('/')[-1],
        "security_groups": security_groups_id_list_as_string,
        "instance_tags": instance_tags_as_string,
        "user_data": UserData,
        "ebsOptimized": ebsOptimized
    }

    root_volume_definition = {}
    additional_volume_definitions = []

    for volume in instance.volumes.all():
        volume_definition = {
            "id": volume.id,
            "device_name": volume.attachments[0]["Device"],
            "type": volume.volume_type,
            "size": volume.size,
            "encrypted": str(volume.encrypted).lower(),
            "iops": volume.iops,
            "snapshot_id": volume.snapshot_id,
            "kms_key_id": volume.kms_key_id
        }

        if volume_definition["device_name"] == "/dev/xvda" or volume_definition["device_name"] == "/dev/sda1":
            root_volume_definition = volume_definition
            root_volume_tags = volume.tags
            root_volume_tags_as_string = ''
            tags_exclusion_keys = []
            for tag in root_volume_tags:
                if tag['Key'] not in tags_exclusion_keys:
                    tag_string = '"' + tag['Key'] + '"' + ' = ' + '"' + tag['Value'] + '"' + '\n\t\t'
                    root_volume_tags_as_string = root_volume_tags_as_string + tag_string
                    
            metadata['root_volume_tags'] = root_volume_tags_as_string

            #return delete_on_termination_flag
            root_volume_config = ec2_client.describe_volumes(VolumeIds=[volume.id])
            metadata['ebs_delete_on_termination'] = str(root_volume_config['Volumes'][0]['Attachments'][0]['DeleteOnTermination']).lower()


        else:
            additional_volume_definitions.append(volume_definition)

    return instance_name, metadata, root_volume_definition, additional_volume_definitions


def template_to_file(template_name, output_path, vars):    
    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, loader=jinja2.FileSystemLoader(f"{os.path.dirname(os.path.realpath(sys.argv[0]))}/_templates"))

    template = env.get_template(f"{template_name}.j2")

    output_file = open(f"{output_path}/{template_name}", "w")
    output_file.write(template.render(vars))

def template_instance(instance_name, output_path, vars):    
    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, loader=jinja2.FileSystemLoader(f"{os.path.dirname(os.path.realpath(sys.argv[0]))}/_templates"))

    template = env.get_template("_instance.tf.j2")

    output_file = open(f"{output_path}/{instance_name}.tf", "w")
    output_file.write(template.render(vars))

def terraform_import(address, specification, working_dir, overwrite_existing):
    statelist = terraform("state", "list", _ok_code=[0, 1], _cwd=working_dir).stdout.decode("ascii")

    if address in statelist:
        logger.debug(f"{address} is already present in the statefile")
        if overwrite_existing:
            logger.debug(f"{address} is being overwritten")
            terraform("state", "rm", address, _cwd=working_dir)
            terraform("import", address, specification, _cwd=working_dir)
    else:
        terraform("import", address, specification, _cwd=working_dir)


@click.command()
@click.option("--tag-key", envvar="TFMA_TAG_KEY", required=True, help="Tag key from the instances to import")
@click.option("--tag-value", envvar="TFMA_TAG_VALUE", required=True, help="Tag key from the instances to import")
@click.option("--base-dir", envvar="TERRAFORM_ROOT_MODULE", default="/work", help="Terraform subfolder")
@click.option("--tf-workspace", envvar="TERRAFORM_WORKSPACE", default="/work", help="Terraform workspace")
@click.option("--aws-profile", envvar="AWS_PROFILE", default="default", help="default")
@click.option("--aws-default-region", envvar="AWS_DEFAULT_REGION", default="ap-southeast-2", help="default")
@click.option("--debug/--no-debug", envvar="TFMA_DEBUG", default=False, help="Enable debug logging")
@click.option("--overwrite-existing/--no-overwrite-existing", envvar="TFMA_OVERWRITE_EXISTING", default=False, help="Overwrite existing files and resources already present in the terraform state file")


def import_instance(tag_key, tag_value, base_dir, tf_workspace, aws_profile, aws_default_region, debug, overwrite_existing):
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger('boto3').setLevel(logging.CRITICAL)
        logging.getLogger('botocore').setLevel(logging.CRITICAL)
        logging.getLogger('urllib3').setLevel(logging.CRITICAL)
        logging.getLogger('sh').setLevel(logging.INFO)

    logger.debug(f"Script Dir: {os.path.dirname(os.path.realpath(sys.argv[0]))}")
    logger.debug(f"Working Dir: {base_dir}")

    click.echo(f"Ensure {base_dir} directory exists...")
    os.makedirs(base_dir, exist_ok=True)



    click.echo("Generating common Terraform files...\n")
    for file in os.listdir("_templates"):


        if file != "_instance.tf.j2":
            if os.path.isfile(f"{base_dir}/{file.removesuffix('.j2')}") and overwrite_existing == False:
                print(f"{base_dir}/{file.removesuffix('.j2')} already exists, skiping...")
                pass
            else:
                template_to_file(file.removesuffix('.j2'), base_dir, {
                        "base_dir": base_dir,
                        "tf_workspace": tf_workspace,
                        "aws_profile": aws_profile,
                        "aws_default_region": aws_default_region })
                print(file.removesuffix('.j2'))

    click.echo(f"\nGetting instance_id list for tag key={tag_key} and value={tag_value}...\n")
    instancelist = list_instances_by_tag_value(tag_key, tag_value)
    for i in instancelist:
        print(i)
    print(f"\nTotal {len(instancelist)} instance(s)")
    
    if instancelist == []:
        print(f"No instances found with tag key={tag_key} value={tag_value}")
        pass
    else:
        count = 0
        for instance_id in instancelist:

            count += 1
            click.echo(f"\nImporting instance {count} of {len(instancelist)}...\nGetting information for instance {instance_id}...")
            instance_name, metadata, root_volume, additional_volumes = get_ec2_info(instance_id)


            click.echo(f"Generating {base_dir}/{instance_name}.tf...")
            if os.path.isfile(f"{base_dir}/{instance_name}.tf") and overwrite_existing == False:
                print(f"{base_dir}/{instance_name}.tf already exists, skiping...")
                pass
            else:
                template_instance(instance_name, base_dir, {
                                "instance_name": instance_name,
                                "metadata": metadata,
                                "root_volume": root_volume,
                                "additional_volumes": additional_volumes,
                                "base_dir": base_dir,
                                "tf_workspace": tf_workspace,
                                "aws_profile": aws_profile,
                                "aws_default_region": aws_default_region })

            click.echo("Initialising Terraform backend...")
            env_vars = os.environ.copy()
            make("_init", _env=env_vars)
            click.echo("Selecting Terraform workspace...")
            make("_workspace", _env=env_vars)

            module_instance_name = instance_name.replace("-", "_")
            click.echo(f"Importing to Terraform state instance {instance_id}...")
            terraform_import(f"module.{module_instance_name}.aws_instance.main", instance_id, base_dir, overwrite_existing)

            for iteration, volume in enumerate(additional_volumes):
                click.echo(f"Importing to Terraform state volume {volume['id']}...")
                terraform_import(f"module.{module_instance_name}.aws_ebs_volume.main[{iteration}]", volume["id"], base_dir, overwrite_existing)
                terraform_import(f"module.{module_instance_name}.aws_volume_attachment.main[{iteration}]", f"{volume['device_name']}:{volume['id']}:{instance_id}", base_dir, overwrite_existing)
            
        click.echo("\nFormatting Terraform code...")
        make("_format", _env=env_vars)

        click.echo("\nImport complete.")


if __name__ == "__main__":
    import_instance()  # pylint: disable=no-value-for-parameter
