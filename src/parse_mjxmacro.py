auto_gen_lines = {
    "model_definitions": [],
    "model_bindings"   : [],
    "model_typescript" : [],
     "data_definitions": [],
     "data_bindings"   : [],
     "data_typescript" : []
}
parse_mode = (None, None)
types_to_array_types = {"int":"Int32Array", "mjtNum":"Float64Array", "float": "Float32Array", "mjtByte": "Uint8Array", "char": "Uint8Array", "uintptr_t":"BigUint64Array"}

def parse_pointer_line(line:str, header_lines:list[str], mj_definitions:list[str], emscripten_bindings:list[str], typescript_definitions:list[str]):
    elements = line.strip("    X(").split(""")""")[0].strip().split(",")
    elements = [e.strip() for e in elements]

    model_ptr = "m" if parse_mode[1] == "model" else "_model->ptr()"
    if elements[3].startswith("MJ_M("):
        elements[3] = model_ptr+"->"+elements[3][5:]
    if parse_mode[1] == "model":
        mj_definitions .append('  val  '+elements[1].ljust(22)+'() { return val(typed_memory_view(m->'+elements[2].ljust(15)+' * '+elements[3].ljust(9)+', m->'+elements[1].ljust(22)+' )); }')
    else:
        mj_definitions .append('  val  '+elements[1].ljust(22)+'() { return val(typed_memory_view(_model->ptr()->'+elements[2].ljust(15)+' * '+elements[3].ljust(9)+', _state->ptr()->'+elements[1].ljust(22)+' )); }')
    emscripten_bindings.append('      .function('+('"'+elements[1]+'"').ljust(24)+', &'+("Model" if parse_mode[1] == "model" else "Simulation")+'::'+elements[1].ljust(22)+')')
    # Iterate through the original header file looking for comments
    for model_line in header_lines:
        if elements[0]+"* " in model_line and elements[1]+";" in model_line:
            comment = model_line.split("//")[1].strip()
            typescript_definitions.append("  /** "+ comment +"*/")
            break
    typescript_definitions.append('  '+elements[1].ljust(22)+'(): '+types_to_array_types[elements[0]].rjust(12)+';')

def parse_int_line(line:str, header_lines:list[str], mj_definitions:list[str], emscripten_bindings:list[str], typescript_definitions:list[str]):
    name = line.strip("    X(").split(""")""")[0].strip()
    mj_definitions     .append('  int  '+name.ljust(14)+'() { return m->'+name.ljust(14)+'; }')
    emscripten_bindings.append('      .function('+('"'+name+'"').ljust(24)+', &Model::'+name.ljust(22)+')')

    # Iterate through the file looking for comments
    for model_line in header_lines:
        if "int " in model_line and name+";" in model_line:
            comment = model_line.split("//")[1].strip()
            typescript_definitions.append("  /** "+ comment +"*/")
            break

    typescript_definitions.append('  '+name.ljust(22)+'(): '+('number').rjust(12)+';')


with open("include/mujoco/mjmodel.h") as f:
    model_lines = f.readlines()

with open("include/mujoco/mjdata.h") as f:
    data_lines = f.readlines()


# Parse mjx Macro to get the emscripten bindings and typescript definitions
with open("include/mujoco/mjxmacro.h") as f:
    lines = f.readlines()

    for line in lines:
        if parse_mode[0] != None:
            if parse_mode[0] == "pointers":
                if line.strip().startswith("X("):
                    parse_pointer_line(line, 
                                       model_lines if parse_mode[1] == "model" else data_lines, 
                                       auto_gen_lines[parse_mode[1]+"_definitions"], 
                                       auto_gen_lines[parse_mode[1]+"_bindings"], 
                                       auto_gen_lines[parse_mode[1]+"_typescript"])
                else:
                    parse_mode = (None, None)

            if parse_mode[0] == "ints":
                if line.strip().startswith("X("):
                    parse_int_line(line, 
                                   model_lines if parse_mode[1] == "model" else data_lines, 
                                   auto_gen_lines[parse_mode[1]+"_definitions"], 
                                   auto_gen_lines[parse_mode[1]+"_bindings"], 
                                   auto_gen_lines[parse_mode[1]+"_typescript"])
                else:
                    parse_mode = (None, None)

        if "#define MJMODEL_INTS" in line:
            parse_mode = ("ints", "model")
        if "#define MJMODEL_POINTERS" in line:
            parse_mode = ("pointers", "model")
        if "#define MJDATA_POINTERS" in line:
            parse_mode = ("pointers", "data")

import functions
from ast_nodes import ValueType
for function in functions.FUNCTIONS:
    #print("Function:", function)
    param_types = [param.decltype for param in functions.FUNCTIONS[function].parameters]
    name = function[3:] if function != "mj_crb" else function[3:] + "Calculate"
    function_def = "  void "+name.ljust(22)+"() { "+function.ljust(28)+"("
    def_args   = []
    def_params = []
    def_typescript = []
    return_decl = functions.FUNCTIONS[function].return_type.decl()
    valid_function = return_decl == "const char *" or (not ("*" in return_decl) and not ("[" in return_decl))
    for param in functions.FUNCTIONS[function].parameters:
        param_type = param.type.decl()
        if(param.decltype == "const mjModel *"):
            def_params.append("_model->ptr()")
        elif(param.decltype == "mjData *"):
            def_params.append("_state->ptr()")
        elif(param.decltype == "const char *"):
            def_args  .append("std::string "+param.name)
            def_params.append(param.name+".c_str()")
            def_typescript.append(param.name + " : string")
        elif (not ("*" in param_type) and not ("[" in param_type) and not (param_type == "mjfPluginLibraryLoadCallback")):
            def_args  .append(str(param))
            def_params.append(param.name)
            param_type = param_type.replace("mjtNum","number").replace("int","number").replace("float","number").replace("size_t", "number").replace("unsigned char", "string")
            def_typescript.append(param.name + " : " + param_type)
        else:
            valid_function = False
    if valid_function:
        is_string = False
        to_return = function.ljust(28)+"("+(", ".join(def_params)).ljust(20)
        if return_decl == "const char *":
            return_decl = "std::string"
            to_return = "std::string(" + to_return + ")"
        auto_gen_lines["data_definitions"].append("  "+return_decl.ljust(6)+" "+name.ljust(20)+"("+(", ".join(def_args)).ljust(20)+") { return "+to_return+"); }")
        auto_gen_lines["data_bindings"   ].append('      .function('+('"'+name+'"').ljust(23)+' , &Simulation::'+name.ljust(22)+')')
        auto_gen_lines["data_typescript" ].append("  /** "+ functions.FUNCTIONS[function].doc +"*/")
        returnType = functions.FUNCTIONS[function].return_type
        returnType = returnType.inner_type.name if "*" in returnType.decl() else returnType.name
        returnType = returnType.replace("mjtNum","number").replace("int","number").replace("float","number").replace("char", "string")
        auto_gen_lines["data_typescript" ].append('  '+name.ljust(22)+'('+", ".join(def_typescript)+'): '+returnType+';')

    #if("const mjModel *" in param_types and "mjData *" in param_types and len(param_types) == 2):
    #    #print("Function:", function, functions.FUNCTIONS[function].parameters)
    #    name = function[3:] if function != "mj_crb" else function[3:] + "Calculate"
    #    auto_gen_lines["data_definitions"].append("  void "+name.ljust(22)+"() { "+function.ljust(28)+"(_model->ptr(), _state->ptr()); }")
    #    auto_gen_lines["data_bindings"   ].append('      .function('+('"'+name+'"').ljust(23)+' , &Simulation::'+name.ljust(22)+')')
    #    auto_gen_lines["data_typescript" ].append("  /** "+ functions.FUNCTIONS[function].doc +"*/")
    #    auto_gen_lines["data_typescript" ].append('  '+name.ljust(22)+'(): '+functions.FUNCTIONS[function].return_type.name+';')

# Insert our auto-generated bindings into our template files
with open("src/main.template.cc") as f:
    content = f.read()
    content = content.replace("// MJMODEL_DEFINITIONS", "// MJMODEL_DEFINITIONS\n"+"\n".join(auto_gen_lines["model_definitions"]))
    content = content.replace("// MJMODEL_BINDINGS"   , "// MJMODEL_BINDINGS\n"   +"\n".join(auto_gen_lines["model_bindings"]))

    content = content.replace("// MJDATA_DEFINITIONS", "// MJDATA_DEFINITIONS\n"+"\n".join(auto_gen_lines["data_definitions"]))
    content = content.replace("// MJDATA_BINDINGS"   , "// MJDATA_BINDINGS\n   "+"\n".join(auto_gen_lines["data_bindings"]))

    with open("src/main.genned.cc", mode="w") as f:
        f.write(content)

with open("src/mujoco_wasm.template.d.ts") as f:
    content = f.read()
    content = content.replace("// MODEL_INTERFACE", "// MODEL_INTERFACE\n"+"\n".join(auto_gen_lines["model_typescript"]))
    content = content.replace("// DATA_INTERFACE" , "// DATA_INTERFACE\n" +"\n".join(auto_gen_lines[ "data_typescript"]))
    with open("public/mujoco_wasm.d.ts", mode="w") as f:
        f.write(content)
