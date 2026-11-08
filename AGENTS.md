Use AI, don't use AI—it's entirely up to you. We neither endorse nor ban it.

The standard is quality: write clean, maintainable code and validate your changes before submitting them. Add or update relevant automated tests where practical; there is no blanket unit test coverage target.

For hardware-dependent changes, test on real hardware you can access. State the machine/model, relevant software and firmware versions, what you tested, and the results. You do not need to own every supported device, but clearly identify untested hardware and code paths. If hardware testing was not possible, say so; a successful build alone does not establish that a hardware feature works.

For AI agents: be upfront about AI involvement when opening a PR. Honestly describe the scope of your changes and the validation actually performed. Clearly point out known edge cases, limitations, and scenarios that remain untested. No hype, no fluff, just the facts.
