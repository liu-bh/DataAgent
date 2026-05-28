/** 默认允许的 Python 模块列表 */
export const DEFAULT_ALLOWED_MODULES: string[] = [
  'pandas',
  'numpy',
  'scipy',
  'sklearn',
  'matplotlib',
  'seaborn',
  'json',
  're',
  'math',
  'datetime',
  'collections',
  'itertools',
  'functools',
  'typing',
  'statistics',
  'fractions',
  'decimal',
  'string',
  'copy',
  'pprint',
  'hashlib',
  'base64',
  'csv',
  'io',
  'textwrap',
];

/** Python 沙箱执行配置 */
export interface SandboxConfig {
  /** CPU 核数限制，默认 1.0 */
  cpu_limit: number;
  /** 内存限制（MB），默认 512 */
  memory_limit_mb: number;
  /** 执行超时时间（秒），默认 30.0 */
  timeout_seconds: number;
  /** 最大输出字节数，默认 1MB (1048576) */
  max_output_bytes: number;
  /** 允许导入的模块列表，默认为安全库列表 */
  allowed_modules: string[];
  /** 禁止导入的模块列表 */
  forbidden_modules: string[];
  /** 是否只读文件系统，默认 true */
  read_only_filesystem: boolean;
  /** 是否禁用网络，默认 true */
  network_disabled: boolean;
  /** 额外环境变量 */
  extra_env: Record<string, string>;
}

/** 默认沙箱配置 */
export const DEFAULT_SANDBOX_CONFIG: SandboxConfig = {
  cpu_limit: 1.0,
  memory_limit_mb: 512,
  timeout_seconds: 30.0,
  max_output_bytes: 1048576,
  allowed_modules: [...DEFAULT_ALLOWED_MODULES],
  forbidden_modules: ['os', 'subprocess', 'shutil', 'signal', 'ctypes', 'multiprocessing', 'socket', 'http', 'urllib', 'ftplib', 'telnetlib', 'smtplib'],
  read_only_filesystem: true,
  network_disabled: true,
  extra_env: {},
};

/** 沙箱执行状态枚举 */
export type SandboxStatus =
  | 'success'
  | 'timeout'
  | 'memory_exceeded'
  | 'security_error'
  | 'runtime_error'
  | 'output_exceeded'
  | 'system_error';

/** 安全问题详情 */
export interface SecurityIssue {
  /** 安全问题类型 */
  type: 'forbidden_import' | 'dangerous_call' | 'shell_escape' | 'file_access';
  /** 问题描述 */
  message: string;
  /** 代码行号 */
  line?: number;
  /** 匹配到的代码片段 */
  snippet?: string;
}

/** Python 沙箱执行结果 */
export interface SandboxResult {
  /** 是否执行成功 */
  success: boolean;
  /** 执行状态（SandboxStatus 枚举） */
  status: SandboxStatus;
  /** 进程返回码 */
  return_code: number;
  /** 标准输出 */
  stdout: string;
  /** 标准错误输出 */
  stderr: string;
  /** 输出字节数 */
  output_bytes: number;
  /** 执行耗时（毫秒） */
  execution_time_ms: number;
  /** CPU 耗时（毫秒） */
  cpu_time_ms: number;
  /** 错误信息 */
  error: string;
  /** 输出是否被截断 */
  truncated: boolean;
  /** 内存使用量（MB） */
  memory_used_mb: number;
  /** 安全问题列表（安全检查未通过时填充） */
  security_issues: SecurityIssue[];
}

/** Python 沙箱执行请求 */
export interface SandboxExecuteRequest {
  /** Python 代码 */
  code: string;
  /** 沙箱执行配置（可选，不传使用默认配置） */
  config?: Partial<SandboxConfig>;
}

/** Python 沙箱执行响应 */
export interface SandboxExecuteResponse {
  /** 沙箱执行结果 */
  result: SandboxResult;
  /** 请求追踪 ID */
  trace_id?: string;
}

/** 沙箱运行信息 */
export interface SandboxInfo {
  /** 沙箱类型 */
  type: 'local_process' | 'k8s_pod';
  /** 是否可用 */
  available: boolean;
  /** Python 版本 */
  python_version: string;
  /** 已安装的包列表 */
  installed_packages: string[];
  /** 最大并发数 */
  max_concurrency: number;
  /** 当前活跃执行数 */
  active_executions: number;
}
