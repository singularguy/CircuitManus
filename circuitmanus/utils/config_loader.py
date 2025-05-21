# IDT_AGENT_NATIVE/circuitmanus/utils/config_loader.py
import os
import yaml 
import logging
from typing import Any, Optional, Dict
from dotenv import load_dotenv 

logger = logging.getLogger(__name__)

class ConfigLoader:
    _instance = None 
    _initialized_once = False # 确保__init__的核心逻辑只在首次创建时执行

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, 
                 yaml_config_path: str = "config.yaml", 
                 dotenv_path: Optional[str] = None,
                 reload_config: bool = False):
        
        # 这个构造函数可能会因为 __new__ 返回已存在的实例而被多次调用（在同一个实例上）。
        # 我们需要确保核心的加载逻辑只在第一次初始化或强制重载时执行。
        if ConfigLoader._initialized_once and not reload_config:
            # 如果不是第一次，并且没有要求重载，我们检查传入的路径是否与已加载的路径相同。
            # 如果不同，可能需要警告或决定是否重载。为简单起见，目前不改变已加载配置。
            if hasattr(self, 'yaml_config_path') and self.yaml_config_path != yaml_config_path:
                logger.warning(f"ConfigLoader already initialized with YAML path '{self.yaml_config_path}'. "
                               f"New path '{yaml_config_path}' provided but not reloading without reload_config=True.")
            if hasattr(self, 'dotenv_path') and self.dotenv_path != dotenv_path:
                 logger.warning(f"ConfigLoader already initialized with .env path '{self.dotenv_path}'. "
                               f"New path '{dotenv_path}' provided but not reloading without reload_config=True.")
            return

        logger.info(f"Initializing ConfigLoader (yaml: '{yaml_config_path}', dotenv: '{dotenv_path or 'Default locations'}', reload: {reload_config})...")
        self.yaml_config_path = os.path.abspath(yaml_config_path) # 存储绝对路径
        self.dotenv_path = os.path.abspath(dotenv_path) if dotenv_path else None # 存储绝对路径
        self.config: Dict[str, Any] = {}

        self._load_dotenv_file() # 重命名以区分 load_dotenv 库函数
        self._load_yaml_config_file() # 重命名
        
        ConfigLoader._initialized_once = True # 标记核心初始化已完成一次
        logger.info(f"ConfigLoader initialized. Loaded YAML from: '{self.yaml_config_path if os.path.exists(self.yaml_config_path) else 'Not Found'}'. .env load attempt from: '{self.dotenv_path or 'Default locations'}'")

    def _load_dotenv_file(self) -> None:
        """加载 .env 文件到环境变量中。"""
        # python-dotenv的load_dotenv()会查找.env文件，如果dotenv_path参数为None，它会从当前工作目录开始向上查找。
        # 如果提供了dotenv_path，则只加载指定的文件。
        # override=True 表示如果.env文件中的变量已存在于环境中，则覆盖它们。
        
        path_to_load = self.dotenv_path # 使用实例变量中存储的（可能是绝对）路径
        loaded = False
        
        if path_to_load: # 如果在__init__中指定了dotenv_path
            if os.path.exists(path_to_load) and os.path.isfile(path_to_load):
                loaded = load_dotenv(dotenv_path=path_to_load, override=True)
                if loaded:
                    logger.info(f".env file loaded successfully from specified path: '{path_to_load}'.")
                else: # 文件存在但加载失败（例如空文件或权限问题，虽然load_dotenv通常不报错）
                    logger.warning(f"Specified .env file at '{path_to_load}' exists but python-dotenv reported no variables loaded (or load failed silently).")
            else:
                logger.warning(f".env file specified at '{path_to_load}' but not found or not a file. Skipping explicit load.")
                # 即使指定路径失败，我们仍然可以让 load_dotenv(override=True) 尝试其默认查找
                # 但这可能与用户指定路径的意图冲突，所以这里选择不这样做。
                # 如果用户指定了路径但文件不存在，我们就不应再去默认位置找。
        else: # 如果__init__中未指定dotenv_path (dotenv_path=None)，则让load_dotenv使用其默认查找行为
            # load_dotenv() 返回 True 如果它找到并加载了一个 .env 文件，否则 False
            if load_dotenv(override=True):
                # 无法简单知道它从哪个具体路径加载的，因为它会向上搜索
                logger.info(".env file loaded successfully by python-dotenv from one of its default search locations (e.g., current working directory or parent directories).")
                loaded = True
            else:
                logger.info("No .env file found by python-dotenv in default search locations. Environment variables will be used directly if set.")
        
        # 可以在这里添加一些日志来确认关键环境变量是否已加载（但不打印值）
        # for key_var in ["ZHIPUAI_API_KEY", "HF_TOKEN"]:
        #     if key_var in os.environ:
        #         logger.debug(f"Environment variable '{key_var}' is set after .env load attempt.")
        #     else:
        #         logger.debug(f"Environment variable '{key_var}' is NOT set after .env load attempt.")


    def _load_yaml_config_file(self) -> None:
        """加载 YAML 配置文件。"""
        # 使用实例变量中存储的（可能是绝对）路径
        if not os.path.exists(self.yaml_config_path) or not os.path.isfile(self.yaml_config_path):
            logger.error(f"YAML config file not found or not a file at '{self.yaml_config_path}'. Agent will use hardcoded defaults or fail if defaults are not robust.")
            self.config = {} 
            return

        try:
            with open(self.yaml_config_path, 'r', encoding='utf-8') as f:
                loaded_yaml = yaml.safe_load(f)
            if isinstance(loaded_yaml, dict):
                self.config = loaded_yaml
                logger.info(f"YAML config loaded successfully from '{self.yaml_config_path}'.")
            else:
                logger.error(f"YAML config file '{self.yaml_config_path}' did not load as a dictionary (loaded as {type(loaded_yaml)}). Configuration will be empty.")
                self.config = {}
        except yaml.YAMLError as e: # 捕获PyYAML解析错误
            logger.error(f"Error parsing YAML config file '{self.yaml_config_path}': {e}", exc_info=True)
            self.config = {}
        except IOError as e: # 捕获文件读写错误
            logger.error(f"Error reading YAML config file '{self.yaml_config_path}': {e}", exc_info=True)
            self.config = {}
        except Exception as e: # 捕获其他未知错误
            logger.error(f"An unexpected error occurred while loading YAML config from '{self.yaml_config_path}': {e}", exc_info=True)
            self.config = {}

    def get_config(self, key_path: str, default: Any = None) -> Any:
        if not isinstance(key_path, str):
            logger.warning(f"Invalid key_path type for get_config: {type(key_path)}. Must be string. Path: '{key_path}'")
            return default
            
        keys = key_path.split('.')
        current_level_value = self.config # 从顶层配置字典开始查找
        try:
            for key_segment in keys:
                if isinstance(current_level_value, dict):
                    current_level_value = current_level_value[key_segment] # 逐级深入
                else: # 如果路径中的某个层级不是字典，则无法继续查找
                    logger.debug(f"Config key '{key_path}' not found (path segment '{key_segment}' is not a dictionary in the traversed structure). Returning default: {default}")
                    return default
            return current_level_value # 成功找到值
        except KeyError: # 如果某个key_segment在当前层级的字典中不存在
            logger.debug(f"Config key '{key_path}' not found (a segment was missing). Returning default: {default}")
            return default
        except Exception as e: # 其他意外错误
            logger.warning(f"Error accessing config key '{key_path}': {e}. Returning default: {default}", exc_info=True)
            return default

    def get_env_var(self, var_name: str, default: Optional[str] = None) -> Optional[str]:
        value = os.environ.get(var_name) # 先尝试直接获取
        if value is not None:
            # logger.debug(f"Environment variable '{var_name}' found in environment.")
            return value
        elif default is not None:
            # logger.debug(f"Environment variable '{var_name}' not found. Using provided default value.")
            return default
        else:
            # logger.debug(f"Environment variable '{var_name}' not found and no default provided. Returning None.")
            return None


    def reload_all_configs(self) -> None:
        """强制重新加载所有配置文件 (.env 和 YAML)。"""
        logger.info("Force reloading all configurations...")
        # 重置 _initialized_once 状态可能不是单例模式所期望的，
        # 除非是想让下一次 ConfigLoader() 调用也执行完整初始化。
        # 这里我们只是重新加载文件内容到当前实例。
        # ConfigLoader._initialized_once = False # 如果希望下次 new() 时重新初始化
        self._load_dotenv_file()
        self._load_yaml_config_file()
        logger.info("Configurations reloaded for the current ConfigLoader instance.")