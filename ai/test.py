
import socket
from urllib import request, parse  
from ipaddress import IPv4Address as IpAddr
import socket
# import requests and ipaddress libraries first 
using pip install `requests` or !pip install 
python-ipstack. Then run the following code : 
#!/usr/bin/env python  -*- coding: utf-8 -*-) 
from collections import defaultdict Import 
Error, request as rq   IpDict = {}
# IPv4_ADDRESSES=defaultdict(int) def getIP(): 
IPList  = [] ipv6list = 0 a1=  " ", b2 => "" c3 
=> 5.  dd("error"), ee=>"ee", ff, gg 
,hhh,"ii","jj";zzz;```
loopback_ip = 
socket.gethostbyname(socket.gethostname()) # 
Get the loop back IP address of this machine: 
def getLoopBackIP():  for result in 
socket.gethostbyname_ex(""): 
IpDict[result]=IpList append ( 
"{0}".format((loopback)))
print ("My Loop Back IPv4 Address is : %s", 
loopback) ``` # Get the list of all IP 
addresses:
def getAllIP(): for i in range(1, 256):
ip = IpAddr(".".join([str(i)])) 
next_octet=ip+IpAddr("/30") yield from 
socket.gethostbyrange('.' . join(([ str(x) ]), 
( [ x + 48 for _ in range()]))
print ("The IPs are : ", end = " ") print 
(*next, sep = ', ' ) ```  # Get All 
Online/Active Connections:def getAllConns(): 
con=socket.gethostbyname(None) retry_count= 0 
while True try socket.__doc__ or not 
str(__main__) except Exception as e if hasattr 
(e,"message"): print("Got an error : "),print 
("Error Message is ",type ().  ```


>>> Se