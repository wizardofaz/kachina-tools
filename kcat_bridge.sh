#!/bin/bash

python src/xmlrpc_proxy_logger.py --proxy-port 7362 --handler src/pykeyer_kcat_bridge.py:handle
