import os
import tempfile

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'rf-tower-system-secret-key-2024')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    UPLOAD_FOLDER = os.environ.get(
        'UPLOAD_FOLDER',
        os.path.join(tempfile.gettempdir(), 'rf_tower_uploads')
    )
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    MAX_FILE_SIZE_MB = 16

    TEMPLATES_AUTO_RELOAD = False
    JSON_AS_ASCII = False
    JSON_SORT_KEYS = True
    JSONIFY_PRETTYPRINT_REGULAR = False


class DevelopmentConfig(Config):
    DEBUG = True
    ENV = 'development'
    TEMPLATES_AUTO_RELOAD = True
    JSONIFY_PRETTYPRINT_REGULAR = True
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')


class ProductionConfig(Config):
    DEBUG = False
    ENV = 'production'


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'rf_tower_test_uploads')


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
