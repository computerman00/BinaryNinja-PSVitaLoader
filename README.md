# BinaryNinja-PSVitaLoader
PS Vita ELF/PRX2 loader plugin for Binary Ninja


### Description:
A Binary Ninja Plugin for PRX2 PS Vita eboot.bin ELFs. 

Dynamic linking of modules on the PS Vita [is preformed](https://wiki.henkaku.xyz/vita/NID#Usage) by NID(**N**umeric **Id**entifier) of a function or variable instead of names. The primary purpose of this plugin is to resolve all import/export function/variable names, create symbols for them, and load them back into the default ELF BinaryView at their respective position. This plugin will also add PS Vita(PRX2) specific datatypes with locations in the binary resolved(if applicable). Additionally, this plugin attempts to do some cleanup resulting from the decompilation of the mixed ARMv7/thumb2 instruction sets, removing some misaligned/junk instructions in places where there should have been in-line data. 

### Plugin use:
Loading the plugin will prompt for a NID database yaml file
![Selecting NID DB](/images/nid-db-select.png)

The included NID database was obtained from the vitasdk [vita-headers](https://github.com/vitasdk/vita-headers) and combined with the following:
```bash
└─$ yq ea '. as $item ireduce ({}; . * $item )' vita-headers/db/360/*.yml > merged-vita-headers-db.yml
```

Afterwards, the plugin will prompt for a header file, this is not necessary however **highly recommended**. With the header file we are able to resolve every single imported functions argument count, argument name, argument type, and function type/return. If this is not used, imported functions default to void and `variable_arguments` is set on the `binaryninja.types.FunctionType` object.
![Selecting NID DB](/images/header-select.png)


The header file included is a compilation of all header files from [vitasdk/vita-headers](https://github.com/vitasdk/vita-headers/), all credit for the headers and NID DB goes to the vitasdk team. This header file was generated using the vitasdk toolchain([LICENSE](https://github.com/vitasdk/vita-headers/blob/master/LICENSE.md) added after) like so:
```
└─$ /usr/local/vitasdk/bin/arm-vita-eabi-gcc -P -E $VITASDK/arm-vita-eabi/include/vitasdk.h -D"__attribute__(x)=" -D"__extension__(x)=" -Drestrict= -D__restrict__= > vitasdk_header.h
```

The plugin will first run linear sweep analysis until no new functions are created. Symbols with their respective function names are then resolved almost instantly and injected/added into the default ELF BinaryView. 


At this point, any sce* function call should be resolved by name, this is incredibly useful for finding specific function calls to patch games or just simply getting a better understanding of the binary for reverse engineering.

### Use-case examples:
A good example(and one of the primary motivations of this project) is to leverage this to patch games to unlock the FPS or allow them to run at full PS Vita resolution. 

Thanks to the talented contributors of VitaGrafix, we can use an already patched game from the VitaGrafix [patchlist](https://github.com/Electry/VitaGrafixPatchlist/blob/master/patchlist.txt) as an educational resource to cross-check our own patches.

EXAMPLE:


Game: Sly Cooper and the Thievius Raccoonus - PCSA00096

Knowing the game runs at `720x408`, we can search for any values set to 0x2d0(720). This results in two finds, thankfully this example is obvious, as 0x198(408) is set right after 720. We do the search in Psuedo C mode but switch to dissasembly to get the exact address:
![Finding resolution in binary](/images/finding_res.png)


Referencing the VitaGrafix patchlist, we confirm these are the correct addresses(Represented as offsets):
```
@FB
0:0xE0AF8 t2_mov(1, 1, fb_w)
0:0xE0AFE t2_mov(1, 1, fb_h)
```


Next, we can search for Vsync(vBlank) related calls. Searching for cross references on `sceDisplayWaitVblankStart` we find that 2 is moved into r0 just before `sceDisplayWaitVblankStartMulti` is called. This likely indicates that the game will wait for 2 vBlank intervals before a VSync, this effectively limits the framerate to half of the displays refresh rate(30fps).
![Cross referencing vBlank calls](/images/vblank_cross_ref.png)

Pseudo-C view(with added vitasdk headers):

![Pseudo-C view](/images/pseudo_c_view.png)



Cross referencing with the patch in VitaGrafix we can confirm our suspicions:
```
@FPS
0:0x10C104 t1_mov(0, vblank)
```
NOTE: In the case of unlocking frame limit, observing the `sceDisplayWaitVblankStart*` call is usually a good start, as this call will wait for the next vblank start, which will occur after the last scanline and before the next VSync interval. However, this isn't always straightforward as many games rely on VSync and modifying anything directly related will usually cause games to speed up. Further research is needed on a binary-to-binary basis. The [VitaGrafixPatchlist](https://github.com/Electry/VitaGrafixPatchlist/blob/master/patchlist.txt) is a great resource for comparing games you have purchased/owned and backed-up to understand how all the talented contributors were able to patch-out FPS caps. 


EXAMPLE:

Another potential method to patch resolution is to cross reference the `sceDisplaySetFrameBuf` symbol and figure out where the framebuffer is updated/set, this takes in a pointer to the `SceDisplayFrameBuf` struct which contains the framebuffer width and height. These are typically set just before the function call. In this example, we can see this game already runs at full resolution as `960x544` is set just prior to the function call. In the majority of games tested(patch applied at run-time via [VitaGrafix](https://github.com/Electry/VitaGrafix)), the following resolutions can be set: `480x272`, `640x368`, `720x408`. 

![example](/images/example.png)

### Notes/Issues:
- Tested to be working on Binary Ninja `4.1.5902-Stable` and `4.2.6075-dev`
- Binary Ninja appears to trip in ARMv7/thumb2 mixed instruction sets binaries. An issue was encountered where if the binary is detected as ARMv7(All were while testing) and the first instruction is a Thumb2 instruction, it will mangle the entire dis-assembled binary. To fix this, right click initial function/instruction->Make Function at This Address->thumb2->linux-thumb2. Next run Linear Sweep again, this will fix the binary and later instruction set switches(typically `blx`) are sometimes accounted for properly.

A painful but much better solution to thumb2 start: After ensuring the very first function(@base_addr) is set to thumb2 manually, I have had great luck doing the following in the BN console:
```
>>> thumb2 = binaryninja.Architecture['thumb2']
... 
>>> thumb2
<arch: thumb2>
>>> for func in bv.functions:
... 	if func.arch != thumb2:
... 		bv.remove_function(func)
```
After all non-thumb2 functions are removed, either (re)load the Vita Loader plugin(recommended) or run a few linear sweeps, this will correctly identify instruction set switches and give you a nice, clean binary view(As originally intended). If anyone knows how to resolve this globally, please do share - I have tried forcing the platform but because the binary is technically `armv7` the platform switches back to `linux-armv7`.


### TODO:
- Change project structure to standardized Binary Ninja plugin structure.
- Extend support to `scelibstub_psp`, `scelibent_psp` and other PRX1 primitives to support the OG PSP.
- Extend to full custom BinaryView plugin with support for relocations
- Potentially extending un-implenented instructions commonly used within Vita/PRX2 elfs(Such as: vcvt, vdiv, vmov, vmrs and other fp related instructions) - UPDATE: The binaryninja team is [already hard at work on these](https://github.com/Vector35/binaryninja-api/commits/dev/arch/armv7).


### Credits:

- The HENkaku [Vita Development Wiki](https://wiki.henkaku.xyz/vita/Main_Page) and specifically the [PRX page](https://wiki.henkaku.xyz/vita/PRX) for the detailed breakdown of the `SceModuleInfo` structure and its location within the ELF. Also for the breakdown of the `scelibent_prx2arm` and `scelibstub_prx2arm` function export/import structures.

- VitaSDK for the [NID db](https://github.com/vitasdk/vita-headers/tree/master/db) and all [header files](https://github.com/vitasdk/vita-headers/tree/master/include)(Also the wonderful vita [toolchain](https://github.com/vitasdk/vdpm) and module [documentation](https://docs.vitasdk.org/modules.html))

- The [VitaLoader Redux](https://github.com/CreepNT/VitaLoaderRedux) project, a Vita loader plugin for Ghidra with way more than just symbol mapping support - although not a Ghidra or Java fan, I studied portions of the project and its amazingly clarifying inline comments when stuck. 



“PlayStation” and "PlayStation Vita" are registered trademarks of Sony Computer Entertainment Inc. This tool is **NOT** affiliated with, endorsed by, related to, or derived from confidential materials belonging to Sony Computer Entertainment Inc.
