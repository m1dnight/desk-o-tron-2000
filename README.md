Desk-O-Tron 2000
================

A webapp that allows you to control the Idasen desk from Ikea. 

You need a Raspberry Pi (or other computer) with bluetooth to run the daemon and webserver. 

![screenshot](deskotron.png)

Initial Setup
=============

1. Pair the desk to your device.
   On a Raspberry Pi,  use `bluetoothctl`, scan for your desk with `scan on`, and then connect on its MAC using `pair <mac>`.
2. Install the dependencies. 
   ```
   python3 -m venv venv 
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the server. 
   ```
   python Main.py
   ```

5. If at some point the bluetooth is acting up, reset the controller.
   `sudo hciconfig hci0 reset`
