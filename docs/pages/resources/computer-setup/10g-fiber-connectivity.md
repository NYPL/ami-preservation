---
title: 10G Fiber Connectivity
layout: default
nav_order: 4
parent: Computer Setup
grand_parent: Resources
---

# Digitization Lab Network Documentation: 10G Fiber Connectivity

## Overview: Understanding "10G Fiber"
Most standard office computers connect to a network at 1 Gigabit (1Gb) speeds. In our digitization lab, we handle massive file sizes—high-resolution scans and video—that would clog a standard connection.

We use **10G Fiber (10 Gigabit Ethernet)**, which is 10 times faster than a standard connection. Instead of sending electrical pulses over copper wire, we send pulses of light over glass strands. This allows us to move gigabytes of data to our servers in seconds rather than minutes.

---

## Hardware Breakdown
Our connectivity relies on a "chain" of four specific components to get the signal from your computer to the wall jack (and eventually the server).

> **⚠️ Hardware Variance Note:**
> While the specific brands listed below (Cisco, ATTO, OWC, Tripp Lite) are our standard deployment, you may encounter different manufacturers depending on when the workstation was built.
> * **Cables:** You may see different colors or brands of Thunderbolt/Fiber cables.
> * **Adapters:** Older machines might use different Thunderbolt chassis models.
> * **Transceivers:** While we prefer Cisco, other compatible brands may be swapped in.
>
> Regardless of the brand name printed on the device, the **functionality and troubleshooting steps remain the same.**

### 1. The Adapter: ATTO ThunderLink NS 3252
* **What it is:** Since our computers don't have built-in fiber ports, this box acts as our external network card.
* **What it does:** It translates the computer’s data into a format the fiber network can understand.
* **Note:** This device is technically capable of 25Gb speeds, but we use it at 10Gb to match our current network infrastructure.

### 2. The Bridge: Thunderbolt 4 Cable (e.g., OWC or similar)
* **What it is:** A high-performance USB-C style cable.
* **What it does:** Connects the computer to the ATTO adapter.
* **Crucial Detail:** Not all USB-C cables are the same. This is a **Thunderbolt** cable, capable of carrying the massive bandwidth required by the adapter. *Do not swap this with a standard phone charging cable; the network will not work.*

### 3. The Translator: SFP+ Transceiver (e.g., Cisco SFP-10G-SR-S)
* **What it is:** A small metal module that plugs into the SFP+ port on the ATTO adapter.
* **What it does:** "SFP" stands for *Small Form-factor Pluggable*. This is the actual laser. It converts the electrical data from the ATTO box into pulses of light (optical signals) to be sent down the fiber cable.
* **Identifying Marks:** You will usually see a **silver metal body** with a black or beige latch mechanism.

### 4. The Highway: Fiber Patch Cable (e.g., Eaton Tripp Lite OM3)
* **What it is:** The aqua-colored cable running from the ATTO adapter to the wall.
* **What it does:** Carries the light signal.
* **Tech Specs:** "OM3" refers to the grade of fiber (Multimode), which is standard for high-speed data over shorter distances.
* **Connector Type:** These use **LC Connectors** (Lucent Connectors), which are the small, square plastic clicks at the ends.

---

## Troubleshooting: The "Cross-Over" Fix
If a computer is physically connected but has no network access (and the amber/green lights on the ATTO box are dark), the most common physical issue is a **Polarity Mismatch**.

### The Concept: Match Light to Dark
Fiber relies on a loop. One strand sends light (**Tx** - Transmit) and the other receives light (**Rx** - Receive).
* Your **Tx** must plug into the wall's **Rx**.
* Your **Rx** must plug into the wall's **Tx**.

If the cables are "straight through" (Tx connects to Tx), the devices are screaming at each other but neither is listening.

### Visual Check: "Laser to No-Laser"
You can verify this by looking at the connectors (carefully—see Safety section below):
1.  **The Source:** Look at the tip of the cable coming *from* the wall. One side will be emitting a faint light (Signal), the other will be dark (Receiver).
2.  **The Destination:** Look at the port on the ATTO box. One port emits light, one is dark.
3.  **The Fix:** You must plug the **Lit Cable** into the **Dark Port**. If you plug Light into Light, the connection will fail.

### How to Swap Pairs (Rolling the Strands)
If you suspect a mismatch, you can "roll" the fiber strands on the patch cable:
1.  **Inspect the Connector:** Look at the plastic connector on the end of the aqua cable. You will see two fibers held together by a plastic clip.
2.  **Unclip:** Gently pry the plastic clip holder apart. The two individual fiber ends (Left and Right) will separate.
3.  **Swap:** Physically swap the Left strand and the Right strand.
4.  **Re-clip:** Snap the plastic holder back onto the connectors.
5.  **Test:** Plug it back into the ATTO adapter. If the link lights turn on (usually solid green or amber), you have solved the polarity issue.

*Note: Only do this on **one end** of the cable (usually the computer end is easier to access).*

---

## ⚠️ Safety Corner: Laser Safety

**Rule #1: Never look directly into the fiber cable.**

* **Why:** The transceivers use infrared lasers. While sometimes visible as a very faint red glow, this light is high-intensity and can damage your retina.
* **How to check for signal safely:**
    * **Check the Link Lights:** Rely on the status LEDs on the ATTO adapter first.
    * **Use Your Phone:** Many smartphone cameras can "see" infrared light. If you need to know if a cable is "live," hold the tip of the cable up to your phone's camera lens (about 2 inches away). You *may* see a purple or pink dot on your phone screen if the laser is active.
    * **Dark is Safe:** If you unplug a cable, the laser usually shuts off automatically (safety feature), but never assume. Treat every fiber cable as if it is "lit."