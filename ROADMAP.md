# GreenThumb Roadmap

## Phase 1: Prototype and validation
- confirm hardware layout and enclosure fit
- validate motion rail and carriage movement
- verify soil sensor placement and I2C addressing
- validate peristaltic pump flow and watering accuracy
- test LED lighting and effect modes
- build the controller stack around Raspberry Pi + Klipper + Python service
- validate automation on four plant zones

## Phase 2: Software maturity
- implement real sensor reading drivers
- add persistent plant profiles per zone
- add watering schedules and thresholds
- track moisture trend history
- build a dashboard with each plant zone status
- add camera capturing and timelapse generation
- implement alerts and diagnostics

## Phase 3: Productization
- improve user experience and UI polish
- harden the physical design and wiring harness
- simplify installation and setup steps
- replace `git pull` with a real update mechanism — see below
- build a service and support process
- create a replacement parts catalog
- define quality control and calibration procedures

### Updates, eventually

Not a near-term task, but worth recording now so the constraint is not
rediscovered later.

`git pull` is not an update mechanism. It brings new source, but the systemd
units, the nginx config, `printer.cfg.example` and any `requirements.txt` change
are only applied by re-running the install script, and the frontend has to be
rebuilt on the device. So a user who pulls gets a partial update, silently, and
the device needs Node and `node_modules` purely to regenerate a static bundle.

What we want instead:

- **Users should not have to SSH in at all.** An update action in the web UI, or
  unattended upgrades, with SSH as the fallback for support rather than the
  supported path.
- **If someone does SSH in, one line should do it** — ideally a Debian package,
  so the whole thing is `sudo apt update && sudo apt upgrade`. A `.deb` can carry
  a prebuilt frontend, the systemd units, the nginx config and the Python deps as
  one versioned artifact, and its `postinst` can do the `printer.cfg`
  backup-and-merge the install script does today.
- **Build the frontend once, in CI, not on every device.** That also drops the
  Node toolchain from the shipped image, and cuts first-boot time — a Vite build
  on a Pi 3 B+ takes considerably longer than on a Pi 4.

**Supported hardware floor: Raspberry Pi 3 Model B+.** That is a deliberate
constraint, and it settles a few things: 1 GB of RAM means the on-device frontend
build still works, so prebuilt bundles are a reliability and install-time
improvement rather than a hardware requirement; 64-bit Pi OS stays the only
target, so a release artifact can be arm64-only; and the board outline, mounting
holes and standard 15-pin CSI connector match the Pi 4, so one enclosure and one
camera ribbon cover both. Anything smaller — Pi 3 A+, Zero 2 W — changes the
mounting pattern and drops to 512 MB, which would reopen the 32-bit question.

Prerequisites whenever this starts: there is no CI yet, and the two version
strings (`pyproject.toml`, `frontend/package.json`) are unmanaged — a release
artifact needs one source of truth for version.

## Phase 4: Commercial launch
- package the product as a sellable smart planter system
- prepare warranty, support, and onboarding docs
- define pricing for hardware + optional subscriptions
- create marketing and brand materials
- test launch in limited pilot sales

## Phase 5: Scale and expand
- add premium versions and new product sizes
- support office/commercial deployments
- add remote monitoring features and managed service offerings
- build a plant analytics and recommendations platform
- expand into a broader indoor plant care ecosystem

## Long-term vision

GreenThumb becomes a product line of smart indoor plant systems for homes, offices, and premium spaces, combining plant care automation, environmental monitoring, and consistent design aesthetics.
