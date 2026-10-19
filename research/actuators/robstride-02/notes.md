# RobStride 02 notes (accessed 2026-10-19)
- Out of budget for a $400 robot: $145/unit [aifitlab](https://aifitlab.com/products/robstride-02-motor); needs 24-60 V supply and CAN (1 Mbps) with USB-CAN adapter.
- Vendor rated/peak = 6/17 N.m (35%); rated speed 360 rpm. Rated vs continuous thermal basis not stated.
- Weight 405 g vs 490 g IP67 variant [pakronics](https://pakronics.com.au/products/robstride-02-qdd-17n-m-integrated-actuator-module-dual-encoders-ss100064875).
- Operating temp upper bound only 50 C (vendor). Failure modes, backlash, thermal data: null (none found).
- ROS2 driver profiles RS00-RS06 checked against official manuals [robstride_ros2](https://index.ros.org/r/robstride_ros2/); CAN protocol details not captured.
