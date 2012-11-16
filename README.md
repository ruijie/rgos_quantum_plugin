rgos_quantum_plugin
===================

Introduction

【BLUEPRINT】: 
https://blueprints.launchpad.net/quantum/+spec/quantum-ruijie-plugin

This plugin implementation provides the following capabilities:

>>Supports the Rgos family of ruijie DC switches
>>Supports KVM with OVS
>>Supports VLAN (Manage whole network L2 VLAN, include VM,vSwitch,Physical Switch)
>>Supports QOS, ACL, Others (TODO)

Pre-requisites

>>OS supported:
    Ubuntu 12.04 (Precise) or above
    Fedora 16 or above (TODO)
    RHEL 6.1 or above (TODO)
>>Control Node :
    2 NIC adapters (100M/1000M)
      eth0 : used with Mananged network
      eth1 : used with VM network
    LLDP Service
    OVS Service
    Internet Service
Demo Virtual Cloud Network System Requirements:

>>1 Control&Compute Node
     1 multi-core processor
     4 GB over of RAM 
     2 physical network adapter

>>1 or more Ruijie DC series Switch

Plugin Installation Instructions
Install with Devstack -- (e.g: Ubuntu 12.04)

1.Git Setup

sudo apt-get install git

2.Devstack Gets Download the Devstack codes,You can use ruijie's setup script:

sudo git clone git://github.com/ruijie/devstack.git

3.Ruijie openstack codes with Folsom Gets

Note: First of all, check your current environment:

•IF you want new create , GOTO 3.1;
•IF you are already have Folsom environment, GOTO 3.2;
•IF you are not Folsom environment, GOTO 3.3;

3.1 New Create (your have not setup any other openstack F codes in your environment)

Download the Ruijie openstack codes(whole compoents version):

sudo git clone git://github.com/ruijie/openstack.f.git

Note: Download Successed , you will get the all ruijie openstack codes include nova , horzion , etc...

3.2 Patch Whole Quantum to current system (you have setuped the openstack enviorment already ):

Download the Ruijie openstack Patch codes (just only quantum components):

sudo git clone git://github.com/ruijie/quantum.git

Note: Download Successed , you will get the whole quantum patch codes include rgos quantum plugins.

3.3 Patch Rgos plugin to current system (you have setuped the openstack enviorment already ):

Download the Ruijie Quantum Plugins Patch codes (just only quantum components):

sudo git clone git://github.com/ruijie/rgos_quantum_plugin.git

Note: Download Successed , you will get the ruijie plugins patch codes include rgos quantum plugins.

1.Ruijie openstack quick setup move the openstack codes into setup path(e.g: /opt/stack)

cd "git local path"(e.g: /home/rj/download/)

cp ./quantum /opt/stack/

Note: you will cover old quantum folder with ruijie quantum patch codes.

2.Setting the config files

Modify the rgos plugin config file:

cd /opt/stack/quantum/etc/quantum/plugins/rgos

sudo vi rgos_quantum_plugin.ini

e.g:

# SQL SETTING

sql_connection = mysql://"user":"password"@127.0.0.1/rgos_quantum

# Network TYPE SETTING

tenant_network_type = vlan

# VLAN RANGE SETTING

network_vlan_ranges = physnet1:1:4094

# OVS integration bridge SETTING 

integration_bridge = br-int

# OVS bridge_mappings SETTING

bridge_mappings = physnet1:br-eth1

# Agent's polling interval in seconds

polling_interval = 2

# Remote Switch SSH server config

# e.g: remote_switch_server ="index":"username":"password":"Switch IP":"SSH Port";

remote_switch_server = 1:rj:rj:192.168.1.15:22;
3.Other necessary prepare

6.1. confirm "eth1" is running

-- check the phynic's status

sudo ifconfig eth1

-- start the phynic if its not running

sudo ifconfig eth1 up

6.2. confirm lldp service is running 

-- check the service status

service lldpd status

-- setup the lldp service if its not exsited

sudo apt-get install lldpd

or

sudo apt-get install lldpad

4.Config the Switch

-- confirm server connected with switch BY "eth1"

check the cable between server's phynic "eth1" and switch's interface.

-- confirm the switch's lldp service is started

(cli) show lldp status

Note: More command about switch , please refer the ruijie switch Configuration guide:LLDP Configuration

http://www.ruijienetworks.com/service/doc-search-list.aspx?SearchType=2&SearchValue=23&SearchValueName=Data+Center+Switches

5.Modify the Setup Script 

-- go to setup script file folder

cd "git local path" (e.g: /home/rj/download/)

cd /devstack

-- Edit the localrc

sudo vi localrc

e.g :

 # Networks Config (your local server ip)
   HOST_IP=192.168.x.x 
   Q_PLUGIN=rgos
   ENABLE_TENANT_VLANS=True   
   PHYSICAL_NETWORK=default    
   OVS_PHYSICAL_BRIDGE=br-eth1
 # Service enable Setting
   ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-net,cinder,c-sch,c-api,c-vol,n-sch,n-novnc,n-xvnc,n-cauth,horizon,mysql,rabbit,quantum,q-svc,q-agt
ls rgos_stack.sh or ls stack.sh

run the setup script ,auto to Setup the openstack system

sudo ./rgos_stack.sh or sudo ./stack.sh 

Auto setup openstack with rgos_stack.sh script . 

It will need spend 10~~30 minutes.

6.IF you get follow success information about setup, the openstack with rgos quantum demo syatem is complete.

+ set +o xtrace


Horizon is now available at http://192.168.x.xx/
Keystone is serving at http://192.168.x.xx:5000/v2.0/
Examples on using novaclient command line is in exercise.sh
The default users are: admin and demo
The password: passwd
This is your host ip: 192.168.x.xx
rgos_stack.sh completed in 176 seconds.
Test the plugin functions
1. open the explorer with URL 

     e.g: http://192.168.x.xx/

2. sign in the ruijie horzion page with your author setting 

     e.g: admin/passwd

3. create network in demo/admin project.

 when network is created , u can check its details ;

4. create instance(VM) in this network.

 runing the INSTANCE.

5. confirm test result.
U can check the kvm server's ovs setting, 
confirm the vlan value is setting in the ovs:

-- confirm instance vnic is created and "tag" property is setted.

>> sudo ovs-vsctl show

e.g : 

Bridge "br-eth1"
    Port "phy-br-eth1"
        Interface "phy-br-eth1"
    Port "eth1"                ==> used for kvm's network device
        Interface "eth1"
    Port "br-eth1"
        Interface "br-eth1"
            type: internal
Bridge br-int
    Port br-int
        Interface br-int
            type: internal
    Port "tape73377aa-a4"        ==> instance create vnic
        tag: 2
        Interface "tape73377aa-a4"
    Port "tap6ba43a44-d7"
        tag: 1
        Interface "tap6ba43a44-d7"
    Port "int-br-eth1"
        Interface "int-br-eth1"

-- confirm instance's "in-port" ,"dl-vlan" and "mod_vlan_vid" property is setted.

>> sudo ovs-ofctl dump-flows br-eth1 

-- confirm instance's "in-port", "dl-vlan" and "mod_vlan_vid" property is setted.

>> sudo ovs-ofctl dump-flows br-int 

  You can check the switch setting by cli:
== confirm the network vlan value is set into switch interface setting :

show vlan 

Note: more test demo information please see follow URL:

 http://blog.sina.com.cn/s/blog_b347cb4a01012ox0.html
Limitations
•The Quantum OVS plugin support quantum network type is "LOCAL" and "VLAN";
•"QOS", "ACL" function now is not support . This work is targeted for Girrzly.
•XenServer is not supported with the current Folsom code.

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------

