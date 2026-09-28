# Health of one component, published at a low rate with qos::state().
# [IF-003] Enumerations are uint8 constants in the message, never magic numbers.
uint8 LEVEL_OK=0
uint8 LEVEL_WARN=1
uint8 LEVEL_ERROR=2
uint8 LEVEL_STALE=3

std_msgs/Header header     # stamp = time of the assessment
string component           # stable identifier, e.g. "left_wheel_driver"
uint8 level                # one of LEVEL_*
string message             # human readable, empty when LEVEL_OK
float64 loop_rate_hz       # [Hz] measured rate of the component's main loop
