from binaryninja import BinaryView, StructureBuilder, Type, log_info

# Slightly hacky approach but works well for now. Maps PyStruct fmt string to Binary Ninja Types
def get_bn_type_from_format(fmt):
    bn_struct_map = {
        'H': Type.int(2, False),  # Unsigned short
        '2s': Type.array(Type.char(), 2),
        '4s': Type.array(Type.char(), 4),
        '26s': Type.array(Type.char(), 26),
        'B': Type.char(),         # Unsigned char
        'I': Type.int(4, False)   # Unsigned int
    }
    return bn_struct_map.get(fmt, Type.void())

def make_bn_struct(fmt, var_names):
    struct = StructureBuilder.create()
    offset = 0
    fmt_pairs = zip(fmt.split(), var_names)

    for f, var in fmt_pairs:
        bn_type = get_bn_type_from_format(f)
        struct.insert(offset, bn_type, var)
        offset += bn_type.width

    return struct




#Common datatypes:
def create_struct(bv: BinaryView, bn_type: str, addr: int):
    if bn_type == "SceLibEnt_prx2arm":
    # Add structs to bn datatypes
        struct_fmt = "B B H H H H H B B B B I I I I"
        struct_vars = [
            "structsize", "reserved1", "version", "attribute", "nfunc",
            "nvar", "ntlsvar", "hashinfo", "hashinfotls", "reserved2",
            "nidaltsets", "libname_nid", "libname", "nidtable", "addtable"
        ]
        scelibent_dt = make_bn_struct(struct_fmt, struct_vars)
        bv.define_user_type("SceLibEnt_prx2arm", Type.structure_type(scelibent_dt))

        #Remove any mis-interpreted instructions(functions) at data_addr
        try:
            rem_func = bv.get_functions_containing(addr)
            bv.remove_function(rem_func[0])
        except:
            log_info("No function at SceLibEnt_prx2arm location")
        scelibent_type = bv.get_type_by_name("SceLibEnt_prx2arm")
        bv.define_data_var(addr=addr,var_type=scelibent_type)

    elif bn_type == "SceLibStub_prx2arm":
        struct_fmt = "B B H H H H H 4s I I I I I I I I I"
        struct_vars = [
            "structsize", "reserved1", "version", "attribute", "nfunc",
            "nvar", "ntlsvar", "reserved2", "libname_nid", "libname",
            "sce_sdk_version", "func_nidtable", "func_table", "var_nidtable",
            "var_table", "tls_nidtable", "tls_table"
        ]
        scelibstub_dt = make_bn_struct(struct_fmt, struct_vars)
        bv.define_user_type("SceLibStub_prx2arm", Type.structure_type(scelibstub_dt))

        #Remove any mis-interpreted instructions(functions) at data_addr
        try:
            rem_func = bv.get_functions_containing(addr)
            bv.remove_function(rem_func[0])
        except:
            log_info("No function at SceLibStub_prx2arm location")
        scelibstub_type = bv.get_type_by_name("SceLibStub_prx2arm")
        bv.define_data_var(addr=addr,var_type=scelibstub_type)

    elif bn_type == "SceModuleInfo_prx2arm":
        struct_fmt = "H 2s 26s B B I I I I I I I I I I I I I I I"
        struct_vars = [
            "modattribute", "modversion", "modname", "terminal", "infoversion",
            "resreve", "ent_top", "ent_end", "stub_top", "stub_end",
            "dbg_fingerprint", "tls_top", "tls_filesz", "tls_memsz",
            "start_entry", "stop_entry", "arm_exidx_top", "arm_exidx_end",
            "arm_extab_top", "arm_extab_end"
        ]
        scemodinfo_dt = make_bn_struct(struct_fmt, struct_vars)
        bv.define_user_type("SceModuleInfo_prx2arm", Type.structure_type(scemodinfo_dt))

        #Remove any mis-interpreted instructions(functions) at data_addr
        try:
            rem_func = bv.get_functions_containing(addr)
            bv.remove_function(rem_func[0])
        except:
            log_info("No function at SceModuleInfo_prx2arm location")
        scemodinfo_type = bv.get_type_by_name("SceModuleInfo_prx2arm")
        bv.define_data_var(addr=addr,var_type=scemodinfo_type)

    #This one is a bit tricky as size varies between 0x20 on FW 0.895, 0x2C on FW 0.931.010, 0x30 on FW 0.945, 0x34 on FW 3.60. We take on the 0x30 default for the time being, tiny errors don't really matter here but TODO: Get size first.
    elif bn_type == "SceProcessParam":
        struct_fmt = "I 4s I I I I I I I I I I"
        struct_vars = [
            "size", "magic", "version", "sdk_version", "*sceUserMainThreadName",
            "sceUserMainThreadPriority", "sceUserMainThreadStackSize", "sceUserMainThreadAttribute",
            "*sceProcessName", "sce_process_preload_disabled", "sceUserMainThreadCpuAffinityMask",
            "*sce_libcparam"#, "unk_0x30"
        ]
        sceprocparam_dt = make_bn_struct(struct_fmt, struct_vars)
        bv.define_user_type("SceProcessParam", Type.structure_type(sceprocparam_dt))

        #Remove any mis-interpreted instructions(functions) at data_addr
        try:
            rem_func = bv.get_functions_containing(addr)
            bv.remove_function(rem_func[0])
        except:
            log_info("No function at SceProcessParam location")
        sceprocparam_type = bv.get_type_by_name("SceProcessParam")
        bv.define_data_var(addr=addr,var_type=sceprocparam_type)

