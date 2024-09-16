# BinaryNinja-PSVitaLoader
PS Vita ELF/PRX2 loader plugin for Binary Ninja


### Plugin use:

Loading the plugin will prompt for a NID database yaml file
![Selecting NID DB](/images/nid-db-select.png)

The included NID database was obtained from the vitasdk [vita-headers](https://github.com/vitasdk/vita-headers) and combined with the following:
```bash
└─$ yq ea '. as $item ireduce ({}; . * $item )' vita-headers/db/360/*.yml > merged-vita-headers-db.yml
```

The plugin will first run linear sweep analysis until no new functions are created. Symbols with their respective function names are then resolved almost instantly and injected/added into the default ELF BinaryView. 


At this point, any sce* function call should be resolved by name, this is incredibly useful for finding specific function calls to patch games or just simply getting a better understanding of the binary for reverse engineering.

### Use-case examples:
A good example(and one of the primary motivations of this project) is to leverage this to patch games to unlock the FPS or allow them to run at full PS Vita resolution. 
Example use-case:
- Searching for the "SceDisplay" functions, we can cross reference the `sceDisplaySetFrameBuf` symbol to figure out where the framebuffer is updated/set, this takes in a pointer to the `SceDisplayFrameBuf` struct which contains the framebuffer width and height. These are typically set just before the function call. In this example, we can see this game already runs at full resolution as `960x544` is set just prior to the function call. In the majority of games tested(patch applied at run-time via [VitaGrafix](https://github.com/Electry/VitaGrafix)), the following resolutions can be set: `480x272`, `640x368`, `720x408`. 

![example](/images/example.png)
NOTE: In the case of unlocking frame limit, observing the `sceDisplayWaitVblankStart` call is usually a good start, as this call will wait for the next vblank start, which will occur after the last scanline and before the next VSync interval. However, this isn't always straightforward as many games rely on VSync and modifying anything directly related will usually cause games to speed up. Further research is needed on a binary-to-binary basis. The [VitaGrafixPatchlist](https://github.com/Electry/VitaGrafixPatchlist/blob/master/patchlist.txt) is a great resource for comparing games you already own, backed-up, and decrypted to understand how all the talented contributors were able to patch-out FPS caps. 



#### Better example:
Thanks to the talented contributors of VitaGrafix, we can use an already patched game from the VitaGrafix [patchlist](https://github.com/Electry/VitaGrafixPatchlist/blob/master/patchlist.txt) as an educational resource to cross-check our own patches.

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

Pseudo-C view:
![Pseudo-C view](/images/pseudo_c_view.png)


Cross referencing with the patch in VitaGrafix we can confirm our suspicions:
```
@FPS
0:0x10C104 t1_mov(0, vblank)
```



### Notes/Issues:
- BInary Ninja appears to trip in ARMv7/thumb2 mixed instruction sets binaries. An issue was encountered where if the binary is detected as ARMv7(All were while testing) and the first instruction is a Thumb2 instruction, it will mangle the entire dis-assembled binary. To fix this, right click initial function/instruction->Make Function at This Address->thumb2->linux-thumb2. Next run Linear Sweep again, this will fix the binary and later instruction set switches(typically `blx`) are accounted for properly.


### TODO:
- Change project structure to standardized Binary Ninja plugin structure.
- Add and improve inline comments to better explain the project 
- Handle different sized function imports([scelibstub_prx2arm](https://wiki.henkaku.xyz/vita/PRX#Imports) vs [scelibstub_prx2arm_new](https://wiki.henkaku.xyz/vita/PRX#Imports)) - currently only supporting size 0x34 `scelibstub_prx2arm` struct, while this has been the case on all tested ELFs, its likely newer/later Vita games are using size 0x24  `scelibstub_prx2arm_new` structs.
- Extend support to `scelibstub_psp`, `scelibent_psp` and other PRX1 primitives to support the OG PSP.
- Extend to full custom BinaryView plugin with support for relocations and potentially extending un-implenented instructions commonly used within Vita/PRX2 elfs(Such as: vcvt, vdiv, vmov, vmrs and other fp related instructions)


### Credits:

- The HENkaku [Vita Development Wiki](https://wiki.henkaku.xyz/vita/Main_Page) and specifically the [PRX page](https://wiki.henkaku.xyz/vita/PRX) for the detailed breakdown of the `SceModuleInfo` structure and its location within the ELF. Also for the breakdown of the `scelibent_prx2arm` and `scelibstub_prx2arm` function export/import structures.

- The [VitaLoader Redux](https://github.com/CreepNT/VitaLoaderRedux) project, a Vita loader plugin for Ghidra with way more than just symbol mapping support - although not a Ghidra or Java fan, I studied portions of the project and its amazingly clarifying inline comments when stuck. 



“PlayStation” and "PlayStation Vita" are registered trademarks of Sony Computer Entertainment Inc. This tool is **NOT** affiliated with, endorsed by, related to, or derived from confidential materials belonging to Sony Computer Entertainment Inc.
