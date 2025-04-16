#!/bin/bash

ssh-keygen -R 18.135.235.162
IP=$(terraform output instance_url | tr -d '"' | sed 's|http://||')
ssh -i ../freud.pem ubuntu@${IP}
