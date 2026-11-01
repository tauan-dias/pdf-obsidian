"""Proteção de rede Linux aplicada antes de importar o motor OCR."""
import ctypes
import errno
import os
from pathlib import Path
import platform
import sys


def restrict_network():
    if not sys.platform.startswith('linux'):
        raise RuntimeError('OCR seguro exige Linux com libseccomp.')
    lib = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    class Arg(ctypes.Structure):
        _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_uint),
                    ('a', ctypes.c_uint64), ('b', ctypes.c_uint64)]
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                         ctypes.c_uint, ctypes.POINTER(Arg)]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x7fff0000)  # ALLOW por padrão
    if not context:
        raise RuntimeError('Falha ao criar filtro de rede OCR.')
    try:
        if lib.seccomp_attr_set(context, 4, 1) != 0:  # SCMP_FLTATR_CTL_TSYNC
            raise RuntimeError('Falha ao sincronizar filtro de rede entre threads.')
        # Bloquear criação de qualquer socket exceto AF_UNIX (comparação NE).
        # Inclui chamadas nativas e filtros herdados por filhos/threads.
        for name in (b'socket', b'socketpair'):
            number = lib.seccomp_syscall_resolve_name(name)
            if number < 0 or lib.seccomp_rule_add_array(context, 0x50000 | errno.EPERM,
                                                       number, 1, ctypes.byref(Arg(0, 1, 1, 0))) != 0:
                raise RuntimeError('Falha ao configurar filtro de rede OCR.')
        # Não permitir usar sockets Unix para alcançar proxies/serviços do host.
        for name in (b'connect', b'ptrace', b'process_vm_readv', b'process_vm_writev', b'pidfd_getfd',
                     b'io_uring_setup', b'io_uring_register', b'io_uring_enter'):
            number = lib.seccomp_syscall_resolve_name(name)
            if number < 0 or lib.seccomp_rule_add_array(context, 0x50000 | errno.EPERM,
                                                       number, 0, None) != 0:
                raise RuntimeError('Falha ao bloquear conexões/inspeção de processos no OCR.')
        if lib.seccomp_load(context) != 0:
            raise RuntimeError('Falha ao ativar filtro de rede OCR.')
    finally:
        lib.seccomp_release(context)


def restrict_filesystem(readable, writable):
    """Landlock ABI 3+: negar acesso fora das árvores explicitamente concedidas.

    Aplicar no processo auxiliar ainda sem threads. Direitos são herdados e não
    podem ser removidos pelo motor, inclusive quando ele chama bibliotecas C.
    """
    if sys.platform != 'linux' or platform.machine() not in ('x86_64', 'aarch64'):
        raise RuntimeError('OCR seguro exige Linux x86_64/aarch64 com Landlock ABI 3+.')
    lib = ctypes.CDLL(None, use_errno=True)
    lib.syscall.restype = ctypes.c_long
    abi = lib.syscall(444, 0, 0, 1)
    if abi < 3:
        raise RuntimeError('OCR seguro exige Landlock ABI 3+ habilitado no kernel.')
    # Direitos de filesystem até TRUNCATE (ABI 3). Não conceder novos direitos
    # de ABI posteriores implicitamente; ioctl em dispositivos fica restrito
    # pelo conjunto mínimo de dispositivos acessíveis.
    handled = (1 << 15) - 1
    read = (1 << 0) | (1 << 2) | (1 << 3)  # EXECUTE, READ_FILE, READ_DIR
    file_rights = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 14)
    class Ruleset(ctypes.Structure):
        _fields_ = [('handled_access_fs', ctypes.c_uint64)]
    class PathRule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]
    attr = Ruleset(handled)
    descriptor = lib.syscall(444, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if descriptor < 0:
        raise OSError(ctypes.get_errno(), 'Falha ao criar política Landlock.')
    try:
        for paths, rights in ((readable, read), (writable, handled)):
            for item in paths:
                path = Path(item).resolve(strict=True)
                fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
                try:
                    rule = PathRule(rights if path.is_dir() else rights & file_rights, fd)
                    if lib.syscall(445, descriptor, 1, ctypes.byref(rule), 0) != 0:
                        raise OSError(ctypes.get_errno(), f'Falha na regra OCR: {path}')
                finally:
                    os.close(fd)
        if lib.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            raise OSError(ctypes.get_errno(), 'Falha ao restringir privilégios OCR.')
        if lib.syscall(446, descriptor, 0) != 0:
            raise OSError(ctypes.get_errno(), 'Falha ao aplicar política Landlock.')
    finally:
        os.close(descriptor)


def restrict_ocr_files(root, workspace):
    root, workspace = Path(root).resolve(), Path(workspace).resolve()
    cache = root / 'cache'
    cache.mkdir(exist_ok=True)
    temporary = workspace / 'tmp'
    temporary.mkdir(exist_ok=True)
    os.environ.update(HOME=str(temporary), TMPDIR=str(temporary),
                      XDG_CACHE_HOME=str(cache), HF_HOME=str(cache))
    import tempfile
    tempfile.tempdir = str(temporary)
    readable = [root, Path(__file__).parent, Path(sys.base_prefix)]
    for name in ('/usr', '/lib', '/lib64', '/proc/self', '/proc/cpuinfo', '/proc/meminfo', '/proc/stat', '/sys',
                 '/etc/ld.so.cache', '/etc/localtime', '/etc/os-release', '/etc/mime.types', '/dev/urandom'):
        if Path(name).exists():
            readable.append(name)
    writable = [workspace, cache, '/dev/null']
    restrict_filesystem(readable, writable)
