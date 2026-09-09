# GreenThumb Product Specification

## Product concept

GreenThumb is a smart indoor planter system designed to automate and optimize plant care for home, office, and premium interior environments. The system combines hardware and software to provide automatic watering, lighting control, environmental visibility, and plant management.

## Target product

A 4-zone smart indoor planter system using:
- modified IKEA VITTSJÖ frame
- melamine lower shelf and glass top shelf
- 1000 mm 2020 aluminum rail mounted behind the plant zones
- GT2 belt and pulley carriage motion system
- NEMA 17 stepper motor with TMC2209 control
- sensorless homing via the motion control board
- four capacitive soil moisture sensors
- I2C address configuration to prevent collisions
- per-zone watering nozzle and peristaltic pump
- addressable LED strip for zone lighting and ambient modes
- Raspberry Pi as host controller
- Pi camera for monitoring and timelapse
- BTT SKR Mini E3 V2 motion board

## Functional goals

### Plant care
- monitor soil moisture for each plant zone
- water plants based on target moisture thresholds
- support custom moisture targets by plant type
- provide low-moisture alerts
- track watering history

### Lighting
- support ambient lighting modes
- support static color modes
- support zone-specific lighting control
- allow schedules for day/night simulations or plant-specific photoperiods

### Motion and positioning
- allow the watering carriage to move to each plant zone
- support homing without endstop dependency via configured crash homing behavior
- support manual control for calibration and maintenance

### Monitoring
- capture status data from sensors and system health checks
- capture camera images and time-lapse content
- show plant condition trends over time

## Non-functional goals

- reliable operation for daily household or office use
- safe fluid handling and non-leaking pump design
- simple maintenance and sensor replacement
- local-first system operation
- scalable architecture for future commercial variants
- production-friendly design and serviceability

## User experience goals

- easy setup in under 15 minutes
- no technical knowledge required for basic operation
- simple one-tap watering or scheduling
- clear status display for each plant zone
- visual plant health insight from camera and moisture history

## Constraints

- must fit within the modified frame geometry
- must use the selected motion system and control board stack
- must remain safe for indoor use
- must avoid overwatering and sensor failures
- must support calibration and maintenance without full disassembly

## Success metrics

- plants remain in target moisture range
- watering events occur only when needed
- LED lighting supports healthy growth routines
- user can easily interact with plant status via dashboard
- system is stable over multi-day automated operation

## Potential future variants

- smaller desktop planter
- larger multi-plant wall system
- premium designer version with custom frame finish
- office commercial unit with centralized management
- agricultural or research prototype variant

## Commercial definition

This is a sellable product category: a smart indoor planter system for people who want healthier plants without manual maintenance. The system is the product; the software is the intelligence layer that enables it.
