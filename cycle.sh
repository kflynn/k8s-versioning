#!/bin/sh

KUBE_VERSION=${1:-1.29}

k3d cluster delete intro

k3d cluster create intro \
    --image +v${KUBE_VERSION} \
    -p "80:80@loadbalancer" -p "443:443@loadbalancer" \
    --k3s-arg '--disable=traefik@server:*;agents:*'