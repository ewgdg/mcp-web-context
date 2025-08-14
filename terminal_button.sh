#!/bin/bash
# Terminal button script for Sway bar

while true; do
    echo '{"version":1}'
    echo '['
    echo '[],'
    echo '[{"full_text":"[Terminal]","color":"#50fa7b","separator":false,"separator_block_width":20},'
    echo '{"full_text":"'$(date +'%Y-%m-%d %I:%M:%S %p')'","color":"#ffffff"}]'
    sleep 1
done