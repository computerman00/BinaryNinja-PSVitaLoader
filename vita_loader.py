from binaryninja import (
    PluginCommand,
    log_error,
    log_info,
    BinaryView,
    Symbol,
    SymbolType,
    Type,
    get_open_filename_input,
    execute_on_main_thread
)
import threading
import struct
import yaml
import os

class VitaElf():

    def __init__(self, bv: BinaryView):
        self.raw = bv.parent_view
        self.bv = bv
        self.nid_database = None
        self.struct_endianness = "<"  # Little endian for struct unpacking



    def load_vita_symbols(self):
        try:
            self.parse_elf()
            self.parse_sce_module_info()
            self.load_nid_database()
            self.process_exports(self.bv)
            self.process_imports(self.bv)
            self.clean_data_segs()

            log_info("Symbols added successfully.")

        except Exception as e:
            log_error(f"Error adding symbols: {e}")


    def parse_elf(self):
        header_data = self.raw.read(0, 0x40)
        log_info(f"Header data len: {len(header_data)}") #TODO debug
        e_ident = header_data[:16]
        self.ei_class = e_ident[4]
        self.ei_data = e_ident[5]

        #make sure its 32-bit
        if self.ei_class != 1:
            raise Exception("Unsupported ELF class (only 32-bit supported)")

        #should always be little endian for vita binaries but will trip on other 32 bit elfs, maybe remove big endian check all together and fall one exception if not littleE.
        if self.ei_data == 1:
            self.struct_endianness = "<"  #littleE
        elif self.ei_data == 2:
            self.struct_endianness = ">"  #bigE
        else:
            raise Exception("Unknown ELF data encoding")

        elf_header_struct = self.struct_endianness + "HHIIIIIHHHHHH"
        elf_header = struct.unpack(elf_header_struct, header_data[16:52])

        (
            self.e_type,
            self.e_machine,
            self.e_version,
            self.e_entry,
            self.e_phoff,
            self.e_shoff,
            self.e_flags,
            self.e_ehsize,
            self.e_phentsize,
            self.e_phnum,
            self.e_shentsize,
            self.e_shnum,
            self.e_shstrndx,
        ) = elf_header
        log_info(f"elf_header struct: {elf_header}") #TODO debug

        #get the program headers.
        self.program_headers = []
        for i in range(self.e_phnum):
            ph_offset = self.e_phoff + i * self.e_phentsize
            ph_data = self.raw.read(ph_offset, self.e_phentsize)
            if len(ph_data) < self.e_phentsize:
                log_error(f"Incomplete program header {i} at offset 0x{ph_offset:X}")
                continue
            ph_struct = self.struct_endianness + "IIIIIIII"
            ph = struct.unpack(ph_struct, ph_data)
            self.program_headers.append(ph)


    def parse_sce_module_info(self):
        #find SceModuleInfo's offset
        module_info_offset = self.get_module_info_offset()
        if module_info_offset is None:
            log_error("Failed to determine SceModuleInfo offset.")
            return None

        module_info_size = 0x5C  #Including SceModuleInfo_common, can adjust later to pull SceModuleInfo_common first
        module_info_data = self.raw.read(module_info_offset, module_info_size)
        if len(module_info_data) < module_info_size:
            log_error("Failed to read complete SceModuleInfo struct.")
            return None

        #Validate SceModuleInfo
        if len(module_info_data) < 0x5c:
            log_error("Invalid SceModuleInfo struct.")
            return None

        #unpacking SceModuleInfo, expanded for easier format character mapping 
        module_info_struct = self.struct_endianness + (
            "H"    # unsigned short modattribute
            "2s"   # unsigned char modversion[2]
            "26s"  # char modname[26]
            "B"    # char terminal
            "B"    # char infoversion
            "I"    # Elf32_Addr reserve
            "I"    # Elf32_Addr ent_top
            "I"    # Elf32_Addr ent_end
            "I"    # Elf32_Addr stub_top
            "I"    # Elf32_Addr stub_end
            "I"    # Elf32_Word dbg_fingerprint
            "I"    # Elf32_Addr tls_top
            "I"    # Elf32_Addr tls_filesz
            "I"    # Elf32_Addr tls_memsz
            "I"    # Elf32_Addr start_entry
            "I"    # Elf32_Addr stop_entry
            "I"    # Elf32_Addr arm_exidx_top
            "I"    # Elf32_Addr arm_exidx_end
            "I"    # Elf32_Addr arm_extab_top
            "I"    # Elf32_Addr arm_extab_end
        )
        SceModuleInfo_unpacked = struct.unpack(module_info_struct, module_info_data)

        (
            self.attributes,    # short modattribute
            self.version,       # char modversion[2]
            modname,            # char modname[26]
            self.type,          # char terminal
            self.gp_value,      # char infoversion
            self.resreve,       # Elf32_Addr resreve
            self.export_top,    # Elf32_Addr ent_top
            self.export_end,    # Elf32_Addr ent_end
            self.import_top,    # Elf32_Addr stub_top
            self.import_end,    # Elf32_Addr stub_end
            self.module_nid,    # Elf32_Word dbg_fingerprint
            self.tls_start,     # Elf32_Addr tls_top
            self.tls_filesz,    # Elf32_Addr tls_filesz
            self.tls_memsz,     # Elf32_Addr tls_memsz
            self.module_start,  # Elf32_Addr start_entry
            self.module_stop,   # Elf32_Addr stop_entry
            self.exidx_top,     # Elf32_Addr arm_exidx_top
            self.exidx_end,     # Elf32_Addr arm_exidx_end
            self.extab_top,     # Elf32_Addr arm_extab_top
            self.extab_end,     # Elf32_Addr arm_extab_end
        ) = SceModuleInfo_unpacked

        self.modname = modname.partition(b'\x00')[0].decode('ascii', errors='ignore')
        self.version = [b for b in self.version]  # Convert version from bytes to list of integers
        

        
        

        
        


    def get_module_info_offset(self):
        ET_SCE_RELEXEC = 0xFE04
        ET_SCE_EXEC = 0xFE00
        ET_SCE_ARMRELEXEC = 0xFFA5
        PT_LOAD = 1

        ''' #Commented this out, only is very rare cases is it e_entry for ET_SCE_EXEC, need more binaries to test and figure out cleaner way to determine SceModuleInfo offset for all cases.
        if self.e_type == ET_SCE_EXEC:
            if self.e_entry == 0: #if self.e_entry != 0:#This isnt always true, only in some cases?
                # SceModuleInfo is at e_entry, havent seen it in current binaries but according to wiki.henkaku.xyz/vita/PRX it can happen.
                return self.e_entry
            else:
                # Use p_paddr - p_offset of the first PT_LOAD segment
                for ph in self.program_headers:
                    p_type = ph[0]
                    p_offset = ph[1]
                    p_paddr = ph[3]
                    if p_type == PT_LOAD:
                        mod_info_offset = p_paddr - p_offset
                        if mod_info_offset >= 0:
                            return mod_info_offset #Can check if None, if so continue
        '''
        #For ET_SCE_RELEXEC and ET_SCE_ARMRELEXEC (AND FOR ET_SCE_EXEC in all test binaries)
        if self.e_type in [ET_SCE_RELEXEC, ET_SCE_ARMRELEXEC, ET_SCE_EXEC]: #Some ET_SCE_EXEC
            #SceModuleInfo struct is in segment indexed by the upper two bits of e_entry
            seg_idx = (self.e_entry >> 30) & 0x3
            seg_offset = self.e_entry & 0x3FFFFFFF
            if seg_idx < len(self.program_headers):
                ph = self.program_headers[seg_idx]
                p_type = ph[0]
                p_offset = ph[1]
                if p_type == PT_LOAD:
                    log_info(f"A p_offset + seg_offset : {p_offset + seg_offset}") #TODO IS THIS ALL USELESS? OFFSET IS JUST 0X1000 in all test elf's
                    return p_offset + seg_offset


    def load_nid_database(self):
        #prompt for yml file
        nid_db_path = get_open_filename_input("Select NID database YAML file")
        if not nid_db_path:
            raise Exception("NID database YAML file is required")

        #load db in class var
        try:
            with open(nid_db_path, "r") as f:
                self.nid_database = yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Failed to load NID database: {e}")

    def process_exports(self, bv: BinaryView):
        log_info("Parsing exports")
        ph_offset = self.program_headers[0][1]
        exports_offset = self.export_top + ph_offset
        exports_end = self.export_end + ph_offset
        log_info(f"Export offset start: {hex(exports_offset)}")
        if not exports_offset or not exports_end:
            log_error("Export sections not defined in SceModuleInfo.")
            return


        while exports_offset < exports_end:
            #Is there even a point of making export size dynamic? Unless we split out _scelibent_ppu_common of size 0x10, could be useful to leave flexibility for potential future integration of scelibent_psp and other PRX1 variants. 
            export_size_data = self.raw.read(exports_offset, 0x20) 
            if len(export_size_data) < 0x20:
                log_error(f"Incomplete export size data at 0x{exports_offset:X}")
                break
            #export_size = struct.unpack("<H", export_size_data)[0]
            export_size = len(export_size_data)
            #This whole read is redundant at the moment, consider extending for variable size or read only once.
            export_data = self.raw.read(exports_offset, export_size)
            if len(export_data) < export_size:
                log_error(f"Incomplete export data at 0x{exports_offset:X}")
                break
            export_struct = self.struct_endianness + "B1BHHHHHBBBBIIII"
            if len(export_data) < struct.calcsize(export_struct):
                log_error(f"Incomplete export structure at 0x{exports_offset:X}")
                break
            export_struct = struct.unpack(export_struct, export_data[:struct.calcsize(export_struct)])
            (
                size,               #unsigned char structsize;
                reserved1,          #unsigned char reserved1[1]; //a.k.a. 'auxattribute'
                version,            #unsigned short version;
                attribute,          #unsigned short attribute;
                num_functions,      #unsigned short nfunc;
                num_vars,           #unsigned short nvar;
                num_tls_vars,       #unsigned short ntlsvar;
                hashinfo,           #unsigned char hashinfo;
                hashinfotls,        #unsigned char hashinfotls;
                reserved2,          #unsigned char reserved2[1];
                nidaltsets,         #unsigned char nidaltsets;
                library_nid,        #Elf32_Word libname_nid;
                library_name_addr,  #Elf32_Addr libname;
                nid_table_addr,     #Elf32_Addr nidtable;
                entry_table_addr,   #Elf32_Addr addtable;
            ) = export_struct

            if attribute == 0x8000 and library_name_addr == 0:
                library_name = "NONAME" #NONAME EXPORT,see: wiki.henkaku.xyz/vita/PRX#NONAME_exports
            else:
                library_name = self.read_string_at(bv, library_name_addr)
            log_info(f"export library_name: {library_name}\nexport struct: {export_struct}") #TODO debug

            for i in range(num_functions):
                nid_addr = nid_table_addr + i * 4
                entry_addr = entry_table_addr + i * 4
                nid_data = bv.read(nid_addr, 4)
                entry_data = bv.read(entry_addr, 4)
                if len(nid_data) < 4 or len(entry_data) < 4:
                    continue
                function_nid = struct.unpack("<I", nid_data)[0]
                function_addr = struct.unpack("<I", entry_data)[0]
                if library_name == "NONAME" and function_nid == 0x935CD196:
                    function_name = "module_start"
                    function_addr -= 1 #Odd off by one byte causes misalignment on NONAME exports. Example: hex(struct.unpack("I",read(entry_table_addr,4)) = 0x8108675d. The module_start should be located at 0x8108675c in this example.
                    log_info(f"module_start addr: {function_addr}") #TODO debug
                else:
                    function_name = self.lookup_nid_function(library_nid, function_nid, library_name)
                self.add_function_symbol(bv, function_addr, function_name)
                log_info(f"export symbol: {function_name}") #TODO debug
                #self.add_function_symbol(bv, function_addr, function_name)


            for i in range(num_vars):
                nid_addr = nid_table_addr + (num_functions + i) * 4
                entry_addr = entry_table_addr + (num_functions + i) * 4
                nid_data = bv.read(nid_addr, 4)
                entry_data = bv.read(entry_addr, 4)
                if len(nid_data) < 4 or len(entry_data) < 4:
                    continue
                variable_nid = struct.unpack("<I", nid_data)[0]
                variable_addr = struct.unpack("<I", entry_data)[0]
                if library_name == "NONAME":
                    if variable_nid == 0x6C2224BA:
                        variable_name = "module_info"
                    elif variable_nid == 0x70FBA1E7:
                        variable_name = "module_proc_param"
                else:
                    variable_name = self.lookup_nid_variable(library_nid, variable_nid, library_name)
                log_info(f"export var: {variable_name} - var addr: {variable_addr}") #TODO
                self.add_data_symbol(bv, variable_addr, variable_name)

            exports_offset += size

    def process_imports(self, bv: BinaryView):
        #process imported funcs
        ph_offset = self.program_headers[0][1]
        imports_offset = self.import_top + ph_offset
        imports_end = self.import_end + ph_offset
        if not imports_offset or not imports_end:
            log_error("Import sections not defined in SceModuleInfo.")
            return


        while imports_offset < imports_end:
            log_info(f"imports_offset: {hex(imports_offset)}") #TODO debug

            import_size_data = self.raw.read(imports_offset, 0x34) #Need to get scemodimport version, hardcoded for now.
            log_info(f"import_size_data: {import_size_data}") #TODO need to actually use this to get size to determine _scelibstub_prx2arm(0x34) or _scelibstub_prx2arm_new(0x24)
            if len(import_size_data) < 2:
                log_error(f"Incomplete import size data at 0x{imports_offset:X}")
                break
            #import_size = struct.unpack("<H", import_size_data)[0] #This may be a good option to figure out, will need to parse struct carefully tho to first get size.
            #TODO: temp for tested binaries/eboot.elf's, need to properly account for _scelibstub_prx2arm_new(size 0x24) which is likely found in later vita games
            import_size = len(import_size_data)

            # TODO: See above, fix so import_size is actually dynamic to account for both _scelibstub_prx2arm(0x34) and _scelibstub_prx2arm_new(0x24). Can potentially be easily expanded to OG PSP binaries as-well(_scelibstub_psp - size: 0x14 or 0x18).
            if import_size == 0x34:
                # _scelibstub_prx2arm
                import_struct = self.struct_endianness + "BBHHHHH4sIIIIIIIII"
                import_struct_size = 0x34
            elif import_size == 0x24:
                # _scelibstub_prx2arm_new
                import_struct = self.struct_endianness + "HHHHHHIIIIIII"
                import_struct_size = 0x24
            else:
                log_error(f"Unknown import size: {import_size} bytes at 0x{imports_offset:X}")
                break


            import_data = self.raw.read(imports_offset, import_size)
            if len(import_data) < import_size:
                log_error(f"Incomplete import data at 0x{imports_offset:X}")
                break

            import_values = struct.unpack(import_struct, import_data[:import_struct_size])

            # Extract import fields based on format
            if import_size == 0x34:
                # _scelibstub_prx2arm - see wiki.henkaku.xyz/vita/PRX#Imports
                (
                    size,                   # unsigned char structsize
                    reserved1,               # unsigned char reserved1
                    version,                # unsigned short version
                    attribute,              # unsigned short attribute
                    num_functions,          # unsigned short nfunc
                    num_vars,               # unsigned short nvar
                    num_tls_vars,           # unsigned short ntlsvar
                    reserved2,              # unsigned char reserved2[4]
                    library_nid,            # Elf32_Word libname_nid
                    library_name_addr,      # Elf32_Addr libname
                    sce_sdk_version,        # Elf32_Word sce_sdk_version
                    func_nid_table_addr,    # Elf32_Addr func_nidtable
                    func_entry_table_addr,  # Elf32_Addr func_table
                    var_nid_table_addr,     # Elf32_Addr var_nidtable
                    var_entry_table_addr,   # Elf32_Addr var_table
                    tls_nid_table_addr,     # Elf32_Addr tls_nidtable
                    tls_entry_table_addr,   # Elf32_Addr tls_table
                ) = import_values
            else:
                # _scelibstub_prx2arm_new
                (
                    size,                   # unsigned short version
                    attribute,              # unsigned short attribute
                    num_functions,          # unsigned short nfunc
                    num_vars,               # unsigned short nvar
                    unknown1,               # unsigned short unknown
                    library_nid,            # unsigned short library_nid
                    library_name_addr,      # Elf32_Addr libname
                    func_nid_table_addr,    # Elf32_Addr func_nidtable
                    func_entry_table_addr,  # Elf32_Addr func_table
                    var_nid_table_addr,     # Elf32_Addr var_nidtable
                    var_entry_table_addr,   # Elf32_Addr var_table
                    # Missing fields TODO: This is wrong. fix struct according to wiki.henkaku.xyz/vita/PRX#Imports
                ) = import_values

            #get lib name
            library_name = self.read_string_at(bv, library_name_addr)
            log_info(f"library_name: {library_name}\nimport_values: {import_values}") #TODO debug

            #process imported functions, lookup by nid, add symbol
            for i in range(num_functions):
                nid_addr = func_nid_table_addr + i * 4
                entry_addr = func_entry_table_addr + i * 4
                nid_data = bv.read(nid_addr, 4)
                entry_data = bv.read(entry_addr, 4)
                if len(nid_data) < 4 or len(entry_data) < 4:
                    continue
                function_nid = struct.unpack("<I", nid_data)[0]
                function_stub_addr = struct.unpack("<I", entry_data)[0]
                function_name = self.lookup_nid_function(library_nid, function_nid, library_name)
                self.add_function_symbol(bv, function_stub_addr, function_name)

            # process imported variables, lookup by nid, add symbol
            for i in range(num_vars):
                nid_addr = var_nid_table_addr + i * 4
                entry_addr = var_entry_table_addr + i * 4
                nid_data = bv.read(nid_addr, 4)
                entry_data = bv.read(entry_addr, 4)
                if len(nid_data) < 4 or len(entry_data) < 4:
                    continue
                variable_nid = struct.unpack("<I", nid_data)[0]
                variable_addr = struct.unpack("<I", entry_data)[0]
                variable_name = self.lookup_nid_variable(library_nid, variable_nid, library_name)
                log_info(f"importing var: {variable_name} - var addr: {variable_addr}") #TODO
                self.add_data_symbol(bv, variable_addr, variable_name)

            imports_offset += size
            


    def lookup_nid_function(self, library_nid, function_nid, library_name):
    #look up function name using nid db - TODO: Figure out more efficient way, nested nightmare
        if self.nid_database and "modules" in self.nid_database:
            for module_name, module in self.nid_database["modules"].items():
                if "libraries" in module:
                    for lib_name, lib in module["libraries"].items():
                        if lib.get("nid") == library_nid:
                            functions = lib.get("functions", {})
                            for func_name, nid in functions.items():
                                if nid == function_nid:
                                    return func_name
        #give default name if not found
        return f"{library_name}_{function_nid:08X}"

    def lookup_nid_variable(self, library_nid, variable_nid, library_name):
    #look up var name using nid db - TODO: Figure out more efficient way, nested nightmare
        if self.nid_database and "modules" in self.nid_database:
            for module_name, module in self.nid_database["modules"].items():
                if "libraries" in module:
                    for lib_name, lib in module["libraries"].items():
                        if lib.get("nid") == library_nid:
                            variables = lib.get("variables", {})
                            for var_name, nid in variables.items():
                                if nid == variable_nid:
                                    return var_name
        #give default name if not found
        return f"{library_name}_{variable_nid:08X}"

    def add_function_symbol(self, bv: BinaryView, addr: int, name: str):
        if not bv.get_function_at(addr):
            bv.create_user_function(addr)
        
        #Setting imports to void and tell binary ninja to resolve variables.
        func_type = Type.function(Type.void(), [], variable_arguments=True)
        
        #Get the function pointer
        func = bv.get_function_at(addr)
        
        #set type to void with variables
        func.type = func_type
        
        symbol = Symbol(SymbolType.ImportedFunctionSymbol, addr, name)
        
        #define as import, will need to add check for export but it appears to just be a color coding thing for our purposes.
        bv.define_imported_function(symbol, func)

    def add_data_symbol(self, bv: BinaryView, addr: int, name: str):
        symbol = Symbol(SymbolType.DataSymbol, addr, name)
        bv.define_user_symbol(symbol)
        # Optionally, define the data variable type
        bv.define_data_var(addr, Type.int(4, sign=False))

    #There has to be a better pythonic way of doing this.
    #Technically would be faster to read into overkill sized buffer and split at b"\x00".
    def read_string_at(self, bv: BinaryView, addr: int):
        #reads until null-terminator from addr.
        s = b""
        while True:
            c = bv.read(addr, 1)
            if c == b"\x00" or not c:
                break
            s += c
            addr += 1
        return s.decode("ascii", errors="ignore")

    def clean_data_segs(self):
        '''
        With the last Linear Sweep run, Binary Ninja mis identifies lots of data segments past import_end as instructions(functions)
        This will remove/undefine those functions.
        '''
        end_imports = self.base_addr + self.import_end
        funcs = self.bv.functions
        for func in funcs:
            if func.start > end_imports:
                self.bv.remove_function(func)

def sweep_before_load(bv):
    '''
    We cannot call bv.update_analysis_and_wait() on a UI thread.
    Until a more clever approach is realized, this will solve two issues:
    1. Loading the plugin and injecting addresses during the initial linear sweep causes mis-alignment issues.
    2. There appears to be an issue with binaries using mixed arm & thumb instruction sets, the first Linear Sweep run does okay but misses many functions(typically on the order of a few thousand). The second run does better and the third will find and create all of them, with the caveat that some inline data will be interpreted as instructions, causing a few non-functions to be represented as mis-aligned functions.
    This function will run linear sweep in a new thread for a max of n times or until no new functions are created.
'''
    def n_linearsweep():
        func_cnt = 0    #function count
        i = 0           #current sweep iteration
        n_max = 3      #max linear sweep runs

        while i < n_max:
            bv.update_analysis_and_wait()           #wait for default analysis
            bv.add_analysis_option("linearsweep")   #add linearsweep
            bv.update_analysis_and_wait()           #run linearsweep and wait

            cur_func_cnt = len(list(bv.functions))  #get current function count
            if cur_func_cnt == func_cnt:
                log_info(f"No new function created at i: {i}")
                break

            func_cnt = cur_func_cnt
            i += 1

        if i >= n_max:
            log_info(f"ran {i} linear sweeps, potentially more functions undiscovered")

        #Switch back to main UI event thread and run plugin
        execute_on_main_thread(lambda: VitaElf(bv).load_vita_symbols())

    #Run linear sweep analysis in new thread.
    threading.Thread(target=n_linearsweep).start()
    
def register_plugin():
    #register plugin after the ARMv7 BinaryView is loaded.

    PluginCommand.register(
        "VitaELF: Inject Symbols",
        "Injects resolved NID symbols into the ARMv7 BinaryView.",
        sweep_before_load
    )

register_plugin()
