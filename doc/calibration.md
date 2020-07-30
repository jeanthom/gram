# Calibrating gram

In order to accomodate various PCB layouts and RAM chips, gram offers a few calibration settings. Those settings are accessible through CSR registers.

## Read delay & burst detection

The DQSBUFM primitive of the ECP5 provides a read delay adjustement. This sets the delay between the moment DQS change its state and DQ datas are sampled. Each DQS group has its own adjustment:
 
 * `rdly_p0` (PHY): read delay for DQS group 0
 * `rdly_p1` (PHY): read delay for DQS group 1

A burst detection mecanism is required to determine the proper values of the read delay. This feature is available in the DQSBUFM primitive, and exposed through the `burstdet` CSR. Each bit of the burstdet CSR corresponds to a DQS group burst detection. The signals in this CSR are latched (ie. when a burst is detected, the corresponding bit stays at 1). You can reset this CSR by writing any value.

Read delay values can be automatically computed by the `gram_auto_calibration()` function in [libgram](../libgram/). They are stored in the `gramProfile` structure.
