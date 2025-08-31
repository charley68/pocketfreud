#!/bin/bash

IP=$(terraform output instance_url | tr -d '"' | sed 's|http://||')
ssh-keygen -R ${IP}
ssh -i ../freud.pem ubuntu@${IP}
