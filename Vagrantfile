# -*- mode: ruby -*-
# vi: set ft=ruby :

# Levanta una VM Ubuntu con Docker y despliega todo el stack con Docker Compose.
Vagrant.configure("2") do |config|
  config.vm.define :servidorWeb do |servidor|
    servidor.vm.box = "bento/ubuntu-22.04"
    servidor.vm.hostname = "servidorWeb"
    servidor.vm.network :private_network, ip: "192.168.50.3"
    servidor.vm.synced_folder ".", "/opt/opscenter"

    servidor.vm.provider "virtualbox" do |vb|
      vb.memory = 2048
      vb.cpus = 2
    end

    servidor.vm.provision "shell", inline: <<-SHELL
      set -e
      if ! command -v docker >/dev/null; then
        curl -fsSL https://get.docker.com | sh
        usermod -aG docker vagrant
      fi
      cd /opt/opscenter
      [ -f .env ] || cp .env.example .env
      sed -i 's#^GRAFANA_PUBLIC_URL=.*#GRAFANA_PUBLIC_URL=http://192.168.50.3:3000#' .env
      sed -i 's#^PROMETHEUS_PUBLIC_URL=.*#PROMETHEUS_PUBLIC_URL=http://192.168.50.3:9090#' .env
      # Red privada host-only: el monitoreo puede escuchar en la IP de la VM
      sed -i 's#^MONITORING_BIND=.*#MONITORING_BIND=0.0.0.0#' .env
      docker compose up -d --build
      echo "Contraseña de admin: $(cat secrets/admin_password)"
    SHELL
  end
end
