FROM python:3.10.0-alpine3.14

ENV PYTHONUNBUFFERED=1
ENV AWS_SDK_LOAD_CONFIG=1

RUN apk add --update --no-cache curl git make

ARG TERRAFORM_VERSION
RUN curl -L -o /tmp/terraform.zip https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip && \
    unzip /tmp/terraform.zip -d /tmp/ && \
    mv /tmp/terraform /usr/local/bin/terraform && \
    chmod +x /usr/local/bin/terraform && \
    rm -rf /tmp/terraform.zip

COPY /requirements.txt /terraform-migration-assistant/requirements.txt
RUN pip3 install -r /terraform-migration-assistant/requirements.txt

COPY / /terraform-migration-assistant

RUN mkdir -p /work
WORKDIR /work

ENTRYPOINT ["python3", "/terraform-migration-assistant/terraform-migration-assistant.py"]
