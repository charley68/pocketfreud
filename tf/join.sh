#!/bin/bash

IP=`terraform output instance_public_ip | tr -d '"'`
ssh -i ../freud.pem ubuntu@${IP}
