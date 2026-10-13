"""Generate test-only owner-constructor adapters from the canonical API model."""
import json

from bindgen import config, gen_api


def generate(folder):
    model = gen_api.Model(json.loads(config.SNAPSHOT_FILE.read_text()))
    owners = sorted(model.owners)
    functions = {name: model.cf[name] for cls in owners for name in model.lifecycle(cls)}
    libraries = sorted({f['library'] for f in functions.values()})
    # Reject a changed signature rather than lose native error injection.
    # Unlike creation with a null parent, deleting a null owner is checked by
    # this pinned native API before dereferencing it.
    probe = model.snap['runtime']['version_method'].split('.')[0]
    trigger = model.lifecycle(probe)[1]
    params = functions[trigger]['params']
    if len(params) != 1 or not params[0]['type'].endswith('*') or params[0]['name'] in functions[trigger].get('null_tested', []):
        raise SystemExit('Constructor error probe requires one mandatory owner argument')
    c = [*(f'#include <{h}>' for h in sorted({f['header'] for f in functions.values()})),
         '#include <assert.h>', '#include <dlfcn.h>', '#include <string.h>',
         f'static void* libraries[{len(libraries)}];',
         f'static int counts[{len(owners)}][3], selected = -1, fired, bad_delete;',
         'void probe_library(int index, const char* path) { libraries[index] = dlopen(path, RTLD_NOW | RTLD_LOCAL); assert(libraries[index]); }',
         '__attribute__((destructor)) static void close_libraries(void) {',
         f'  for (int i = {len(libraries)}; i-- > 0;) if (libraries[i]) dlclose(libraries[i]);', '}',
         'static void* symbol(int index, const char* name) { void* p = dlsym(libraries[index], name); assert(p); return p; }',
         '#define REAL(index, name) ((__typeof__(&name))symbol(index, #name))',
         'void probe_begin(int which) { memset(counts, 0, sizeof(counts)); selected = which; fired = bad_delete = 0; }',
         'int probe_metric(int owner, int column) { if (owner < 0) return column ? bad_delete : fired; return counts[owner][column]; }']
    mojo = ['"""Generated owner fault adapters; test use only."""',
            'from std.ffi import OwnedDLHandle, _DLCallable',
            'from cvc5_mojo._c.raw import c_api',
            'from cvc5_mojo._c.ffi import Ptr, c_bytes, library_path',
            f'comptime OWNER_COUNT = {len(owners)}',
            *(f'comptime {cls}_ID = {index}' for index, cls in enumerate(owners)),
            'def install(shim: OwnedDLHandle) raises:', '    var api = c_api()']
    for index, library in enumerate(libraries):
        mojo += [f'    var path_{index} = c_bytes(library_path("{library}"))',
                 f'    shim.get_function[NoneType]("probe_library")(Int32({index}), path_{index}.unsafe_ptr())']
    for index, cls in enumerate(owners):
        for column, name in enumerate(model.lifecycle(cls)):
            f = functions[name]
            params = f['params']
            signature = ', '.join(f'{p["type"]} {p["name"]}' for p in params) or 'void'
            args = ', '.join(p['name'] for p in params)
            call = f'REAL({libraries.index(f["library"])}, {name})({args})'
            c.append(f'{f["returns"]} test_{name}({signature}) {{')
            if column == 0:
                c += [f'  ++counts[{index}][0];', f'  if (selected == {index}) {{',
                      '    ++fired;',
                      f'    REAL({libraries.index(functions[trigger]["library"])}, {trigger})(NULL);',
                      '    return NULL;', '  }', f'  {f["returns"]} result = {call};',
                      f'  if (result) ++counts[{index}][1];', '  return result;']
            else:
                c += [f'  if (!{params[0]["name"]}) {{ ++bad_delete; return; }}',
                      f'  ++counts[{index}][2];', f'  {call};']
            c.append('}')
            result = 'Ptr' if column == 0 else 'NoneType'
            mojo.append(f'    api[]._{name} = rebind[_DLCallable[{result}, MutUntrackedOrigin]](shim.get_function[{result}]("test_{name}"))')
    source = folder / 'owner-faults.c'
    source.write_text('\n'.join(c) + '\n')
    (folder / 'owner_fault_support.mojo').write_text('\n'.join(mojo) + '\n')
    return source
