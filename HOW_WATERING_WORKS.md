# How GreenThumb Decides to Water

This explains, in plain language, how the planter figures out that a plant is
thirsty and what it does about it. No programming knowledge needed.

## The short version

Every minute, the planter checks how wet the soil is in each pot. It doesn't act
on any single check — it looks at the average of the last ten. If that average
says a plant is drier than you asked it to be, the watering arm slides over to
that pot and runs the pump for a measured number of seconds. Then it leaves that
plant alone for half an hour before it will consider watering it again.

That's the whole idea. The rest of this document explains why each of those
pieces is there.

## How it measures thirst

Each pot has a probe stuck in the soil. The probe doesn't measure water
directly — it measures how easily an electrical signal passes through the soil
around it, which changes depending on how wet that soil is. Wet soil and dry
soil give very different signals, and that difference is what we use.

The probe reports a plain number, roughly between 350 and 1000:

| Reading | What it means |
|---|---|
| ~350 | Bone dry — this is what the probe reads sitting in open air |
| ~650 | Comfortably damp |
| ~1000 | Soaking — this is what it reads sitting in a glass of water |

Those two ends, 350 and 1000, are the scale. The planter converts every reading
onto a 0–100% scale using them, so 350 becomes 0% and 1000 becomes 100%. When
the app shows you "43% moisture," that's where the raw reading falls between
bone dry and underwater.

One thing worth knowing: **soil never reaches 100%.** Plain water conducts better
than even soaking wet dirt, so a freshly watered pot might read 80%. That's
normal and it's the safe direction to be wrong in — the planter will never
mistake damp soil for wet enough.

## Why it averages ten readings instead of trusting one

A single reading can be wrong. The probe can be briefly disturbed, electrical
noise can nudge the number, or a pocket of water can sit against the probe while
the rest of the pot is dry. Acting on one bad reading means watering a plant that
didn't need it.

So the planter keeps the last ten readings for each pot and uses their average.
Since it checks once a minute, **the average covers the last ten minutes.** A
single odd number barely moves a ten-number average, but genuine drying — which
happens over hours — moves it steadily.

It also refuses to water at all until it has collected all ten readings. That
means for the first ten minutes after the planter is switched on or restarted,
it will watch but never water. This is deliberate: right after a restart it has
no history, and no history means no way to tell a real trend from a fluke.

## What has to be true before it waters

Every minute, for each pot, the planter asks five questions in order. **All five
must be yes** or it moves on and tries again next minute.

1. **Do I have ten readings yet?** If it just started up, no — wait.
2. **Is the ten-minute average below the target for this plant?** Each pot has
   its own target, because a fern and a succulent don't want the same thing.
3. **Has it been at least 30 minutes since I last watered this pot?** See below.
4. **Is there actually water to pump?** A sensor clipped to the supply tube says
   whether water is reaching the pump. If the reservoir has run dry, the planter
   stops here rather than running a pump that has nothing to move.
5. **Did the arm actually reach the pot?** If the arm can't move — it isn't
   calibrated, something is in the way — the planter refuses to run the pump.
   Watering the wrong spot is worse than not watering.

Only then does the pump run.

Question 4 is the one that stops a specific kind of lie. Without it, an empty
reservoir looks exactly like a successful watering: the pump runs, nothing comes
out, and the planter records that your plant was watered. Everything else here
fails loudly; that one failed silently.

## The half-hour wait, and why it matters

This is the rule that keeps a plant from drowning, and it's worth understanding.

When the pump runs, the soil doesn't change instantly — water takes time to
spread from where it lands to where the probe is sitting. On top of that, the
planter is using a ten-minute average, so even once the soil *is* wetter, it
takes a full ten minutes for that to show up in the average.

Without a waiting rule, here's what would happen: the planter waters, checks
again a minute later, still sees a dry average, and waters again. And again.
Roughly ten doses would go into a pot that needed one.

So after watering a pot, that pot is off-limits for 30 minutes. Long enough for
the water to spread and for the average to catch up to reality.

## One job at a time

The planter has one watering arm and one pump, and it can only be in one place
at a time. So everything that touches the hardware — reading probes, moving the
arm, running the pump — takes turns. Nothing ever happens simultaneously.

If you press a button in the app while the planter is in the middle of an
automatic watering cycle, **your request is refused rather than queued.** You'll
see a message saying the hardware is busy. This is on purpose: a button you
pressed that quietly runs four minutes later, after you've walked away and
forgotten about it, is worse than one that tells you to try again.

The same applies in reverse. If you're moving the arm by hand, the automatic
check skips that minute entirely rather than fighting you for control. It picks
up again on the next pass.

## Reading the numbers in the app

| What you see | What it means |
|---|---|
| A percentage | How wet that pot is, 0% = bone dry, 100% = underwater |
| **-1** | No reading. The probe is unplugged, broken, or not installed |
| Sample count below 10 | Still gathering history — won't water until this hits 10 |
| "Hardware is busy" | Something else is using the arm or pump; try again shortly |

**-1 never means dry.** It means "I don't know," and the planter treats it that
way — a pot reporting -1 is skipped entirely rather than watered. If a probe
falls out, the plant doesn't get flooded; it just stops being monitored. If you
see -1 where you expect a number, check that the probe is plugged in.

Probes can also be plugged in while the planter is running. It notices a new one
within a minute and starts including it — no restart needed.

## Turning automatic watering on

**It ships turned off.** The planter will measure, record, and display
everything, but it will not run the pump on its own until someone deliberately
enables it. Everything described above is what happens *once it's on*.

This is intentional. Automatic watering should be switched on only after the
pump has been tested by hand and the flow rate has been measured, because the
planter converts "give this plant 100 mL" into "run the pump for this many
seconds." If it thinks the pump is twice as fast as it really is, every plant
gets half as much water as intended, forever, and nothing about that looks
broken from the outside.

## If something goes wrong

The design assumes things will fail and tries to fail toward *not watering*
rather than toward flooding:

- **A probe stops responding.** That pot reports -1 and is skipped. The planter
  also quietly retries it every minute, so a loose connector that reseats itself
  recovers on its own.
- **The arm can't move.** The pump doesn't run. No water goes anywhere.
- **The reservoir runs dry.** The supply sensor reports it, the pump doesn't run,
  and the planter keeps checking every minute — so it resumes on its own once you
  refill, with no cooldown to wait out, because no watering actually happened.
  A sensor that stops answering is treated the same as a dry line: the planter
  would rather skip a watering than run the pump on a guess.
- **The connection to the motion board drops mid-pour.** The pump is commanded
  off regardless, and the board is configured to shut the pump off by itself if
  it loses contact with the software. Two independent stops, because a pump stuck
  running is the one failure here that empties a reservoir onto your floor.
- **The automatic check itself hits an error.** It's logged, that minute is
  skipped, and checking continues. One bad minute never stops the planter for
  good.

The failure this design does *not* protect against is a wrong flow rate, because
nothing about it looks like an error — the planter reports success every time
while quietly delivering the wrong amount. That's why measuring it by hand
matters more than it sounds like it should.
