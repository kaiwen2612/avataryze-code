conda activate avataryze
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 3000
sudo systemctl restart avataryze.service