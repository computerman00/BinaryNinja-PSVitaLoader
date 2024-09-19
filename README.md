# BinaryNinja-PSVitaLoader
PS Vita ELF/PRX2 loader plugin for Binary Ninja

## Table of Contents
1. [Description](#description)
2. [Plugin Usage](#plugin-usage)
3. [Notes/Issues](#notesissues)
4. [TODO](#todo)
5. [Credits](#credits)
6. [Use-case examples](#use-case-examples)
7. [Legal](#legal)

### Description:
A Binary Ninja Plugin for PRX2 PS Vita eboot.bin ELFs. 

Dynamic linking of modules on the PS Vita [is performed](https://wiki.henkaku.xyz/vita/NID#Usage) by NID(**N**umeric **Id**entifier) of a function or variable instead of names. The primary purpose of this plugin is to resolve all import/export function/variable names, create symbols for them, and load them back into the default ELF BinaryView at their respective position. This plugin will also add PS Vita(PRX2) specific datatypes with locations in the binary resolved(if applicable). Additionally, this plugin attempts to do some cleanup resulting from the decompilation of the mixed ARMv7/thumb2 instruction sets, removing some misaligned/junk instructions in places where there should have been in-line data. 


### Plugin Usage:
Loading the plugin will prompt for a NID database yaml file
![Selecting NID DB](/images/nid-db-select.png)

The included NID database was obtained from the vitasdk [vita-headers](https://github.com/vitasdk/vita-headers) and combined with the following:
```bash
└─$ yq ea '. as $item ireduce ({}; . * $item )' vita-headers/db/360/*.yml > merged-vita-nid-db.yml
```

Afterwards, the plugin will prompt for a header file, this is not necessary, however **highly recommended**. With the header file we are able to resolve every single imported functions argument count, argument name, argument type, and function type/return. If this is not used, imported functions default to void and `variable_arguments` is set on the `binaryninja.types.FunctionType` object.

![Selecting NID DB](/images/header-select.png)

The header file included is a compilation of all header files from [vitasdk/vita-headers](https://github.com/vitasdk/vita-headers/), all credit for the headers and NID DB goes to the vitasdk team. This header file was generated using the vitasdk toolchain([LICENSE](https://github.com/vitasdk/vita-headers/blob/master/LICENSE.md) added after) like so:
```
└─$ /usr/local/vitasdk/bin/arm-vita-eabi-gcc -P -E $VITASDK/arm-vita-eabi/include/vitasdk.h -D"__attribute__(x)=" -D"__extension__(x)=" -Drestrict= -D__restrict__= > vita_headers.hpp
```

The plugin will first run linear sweep analysis until no new functions are created. Symbols with their respective function names are then resolved almost instantly and injected/added into the default ELF BinaryView. 


At this point, any sce* function call should be resolved and a few datatypes will be added. If the header file was supplied, all datatypes will be imported along with the sce* functions proper return type, argument names, and argument types. 
![Plugin Sample](/images/plugin-sample.png)


### Notes/Issues:
- Tested to be working on Binary Ninja `4.1.5902-Stable` and `4.2.6075-dev`
- Binary Ninja appears to trip in ARMv7/thumb2 mixed instruction sets binaries. An issue was encountered where if the binary is detected as ARMv7(All were while testing) and the first instruction is a Thumb2 instruction, it will mangle the entire dis-assembled binary. To fix this, right click initial function/instruction->Make Function at This Address->thumb2->linux-thumb2. Next run Linear Sweep again, this will fix the binary and later instruction set switches(typically `blx`) are sometimes accounted for properly.

A painful but much better solution to thumb2 start: After ensuring the very first function(@base_addr) is set to thumb2 manually, I have had great luck doing the following in the BN console:
```python
>>> thumb2 = binaryninja.Architecture['thumb2']
... 
>>> for func in bv.functions:
... 	if func.arch != thumb2:
... 		bv.remove_function(func)
```
After all non-thumb2 functions are removed, either (re)load the Vita Loader plugin(recommended) or run a few linear sweeps, this will correctly identify instruction set switches and give you a clean binary view(for the most part). If anyone knows how to resolve this globally, please do share - I have tried forcing the platform but because the binary is technically `armv7` the platform switches back to `linux-armv7`.


### TODO:
- Split functions and utility across multiple imports to maintain readability.
- Move examples to wiki
- Extend support to `scelibstub_psp`, `scelibent_psp` and other PRX1 primitives to support the OG PSP.
- Extend to full custom BinaryView plugin with support for relocations
- ~~Potentially extending un-implenented instructions commonly used within Vita/PRX2 elfs(Such as: vcvt, vdiv, vmov, vmrs and other fp related instructions)~~ - The binaryninja team is [already hard at work on these](https://github.com/Vector35/binaryninja-api/commits/dev/arch/armv7).


### Credits:

- The HENkaku [Vita Development Wiki](https://wiki.henkaku.xyz/vita/Main_Page) and specifically the [PRX page](https://wiki.henkaku.xyz/vita/PRX) for the detailed breakdown of the `SceModuleInfo` structure and its location within the ELF. Also for the breakdown of the `scelibent_prx2arm` and `scelibstub_prx2arm` function export/import structures.

- VitaSDK for the [NID db](https://github.com/vitasdk/vita-headers/tree/master/db) and all [header files](https://github.com/vitasdk/vita-headers/tree/master/include)(Also the wonderful vita [toolchain](https://github.com/vitasdk/vdpm) and module [documentation](https://docs.vitasdk.org/modules.html))

- The [VitaLoader Redux](https://github.com/CreepNT/VitaLoaderRedux) project, a Vita loader plugin for Ghidra with way more than just symbol mapping support - although not a Ghidra or Java fan, I studied portions of the project and its amazingly clarifying inline comments when stuck. 


### Use-case examples:
There are many great use-cases to learning more about reverse engineering binaries, a good example is to leverage this to patch binaries to unlock the FPS or allow them to run at full PS Vita resolution. 

Thanks to the talented contributors of [VitaGrafix](https://github.com/Electry/VitaGrafix), we can patch binaries directly on the Vita at loadtime. The VitaGrafix [wiki](https://github.com/Electry/VitaGrafix/wiki/The-VG-Language%E2%84%A2) serves as a great educational resource to get started on this.

EXAMPLE:

Patching FPS limits:
Searching for cross references on vBlank(vSync) related calls is usually a good start. In a lot of cases, the frame limit is introduced by setting a vblank interval greater than `1`. Typically this would be done with a value moved into `r0` just before `sceDisplayWaitVblankStartMulti` is called. This value(`vcount`) will typically be `1`, `2`, or `3`. This likely indicates the wait for the next vblank start, which will occur after the last scanline and before the next VSync interval. A `vcount` of `2` will wait for `2` vBlank intervals before a VSync, this effectively limits the framerate to half of the displays refresh rate(30fps). A `vcount` of `3` would be refresh-rate/3, effectively limiting to 20fps.

Looking at the popular [nzportable](https://github.com/nzp-team/nzportable) homebrew game running at 60fps natively.

![nzp fps](/images/example2-fps.png)

The variable here wasn't resolved, however looking at the data at that address, we see its just a `1`, this indicates the game is capped to the screens refresh rate(60Hz), as 1 vBlank interval will occur for every vSync interval. 

![nzp fps var](/images/example2-fps-data.png)

NOTE: This isn't always straightforward as many binaries will rely on VSync and modifying anything directly related will usually cause them to run at double speed. Further research is needed on a binary-to-binary basis. 


Patching resolution:
This is much simpler and typically you'd want to load up the binary on a PS Vita with a tool that can poll the frame buffer to determine resolution. Knowing the resolution, you can simply search for that value within Binary Ninja. Looking at the nzp homebrew again, knowing it runs at full Vita resolution of `960x544`, we can search for `0x3c0`(960), this results in only one find and thankfully its a bit more obvious, as `0x3c0`(960) is set just before `0x220` (544)

![nzp res](/images/nzp-find-res.png)



Another potential method to patch resolution is to cross reference the `sceDisplaySetFrameBuf` symbol and figure out where the framebuffer is updated/set, this takes in a pointer to the `SceDisplayFrameBuf` struct which contains the framebuffer width and height. These values are sometimes set just before the function call. According to the [vitasdk documentation](https://docs.vitasdk.org/group__SceDisplayKernel.html#structSceDisplayFrameBuf) the following resolutions can be set: `480x272`, `640x368`, `720x408`, `960x544`. 

To show an example of this and practice our reverse engineering, we use the vitasdk toolchain to compile a homebrew app with a resolution of 640(`0x280`) x 368(`0x170`).


Searching for `0x280`, there is only one with `0x170` next to it, making it the obvious choice:
```
8103d040      int32_t var_44 = 0x280;
8103d044      int32_t var_40 = 0x170;
8103d048      sceDisplaySetFrameBuf(&var_54, SCE_DISPLAY_SETBUF_NEXTFRAME);
```

Looking at the disassembly we see that `0x280` is moved into r1 at addr `0x8103d036` and `0x170` is moved into `r2` at addr `0x8103d03c` before they are both stored on the stack.
```
8103d036  5ff42071   movs    r1, #0x280
8103d03a  0192       str     r2, [sp, #4] {var_48}  {0x0}
8103d03c  5ff4b872   movs    r2, #0x170
8103d040  0291       str     r1, [sp, #8] {var_44}  {0x280}
8103d042  00a8       add     r0, sp, #0 {var_54}
8103d044  0392       str     r2, [sp, #0xc] {var_40}  {0x170}
8103d046  0121       movs    r1, #1
8103d048  e4f14eeb   blx     #sceDisplaySetFrameBuf
```

We could use this information to patch the binary by changing the values in the `mov` instructions, or we can patch this directly on the Vita with VitaGrafix. Instead of patching with a set value, VitaGrafix allows us to use a dynamic variable that can be configured before starting the binary, allowing it to patch the binary at load-time. This patch would look like:

```
[CUSTHOMBRW, eboot.bin]
@FB
0:0x3d036 t2_mov(1, 1, fb_w)
0:0x3d03c t2_mov(1, 2, fb_h)
```


### Legal

“PlayStation” and "PlayStation Vita" are registered trademarks of Sony Computer Entertainment Inc. This tool is **NOT** affiliated with, endorsed by, related to, or derived from confidential materials belonging to Sony Computer Entertainment Inc.

This tool was created for educational, security research purposes. Anything mentioned in this repository, any examples shown, and the plugin itself will **NOT** and can **NOT** break any encryption or circumvent protections in a binary.
