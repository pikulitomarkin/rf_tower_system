import os
import logging

import matplotlib
matplotlib.use('Agg')

from flask import Flask, jsonify, render_template
from flask_cors import CORS

from config import config_by_name


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "max_age": 3600,
        }
    })

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app.logger.setLevel(logging.INFO)

    from routes.kmz_routes import kmz_bp
    from routes.rf_routes import rf_bp

    app.register_blueprint(kmz_bp, url_prefix='/api/kmz')
    app.register_blueprint(rf_bp, url_prefix='/api/rf')

    register_error_handlers(app)
    register_main_routes(app)

    app.logger.info('RF Tower System iniciado com sucesso')
    return app


def register_error_handlers(app):

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'error': 'bad_request',
            'message': 'Requisição inválida. Verifique os dados enviados.',
            'details': str(error) if str(error) else None
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'not_found',
            'message': 'O recurso solicitado não foi encontrado.',
            'details': str(error) if str(error) else None
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'success': False,
            'error': 'method_not_allowed',
            'message': 'Método HTTP não permitido para esta rota.',
            'details': str(error) if str(error) else None
        }), 405

    @app.errorhandler(413)
    def payload_too_large(error):
        return jsonify({
            'success': False,
            'error': 'file_too_large',
            'message': 'O arquivo enviado excede o tamanho máximo de 16 MB.',
            'details': 'MAX_CONTENT_LENGTH = 16 MB'
        }), 413

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f'Erro interno do servidor: {error}')
        return jsonify({
            'success': False,
            'error': 'internal_server_error',
            'message': 'Ocorreu um erro interno no servidor. Tente novamente mais tarde.',
            'details': str(error) if app.config.get('DEBUG') else None
        }), 500

    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        app.logger.error(f'Exceção não tratada: {error}', exc_info=True)
        return jsonify({
            'success': False,
            'error': 'unexpected_error',
            'message': 'Ocorreu um erro inesperado.',
            'details': str(error) if app.config.get('DEBUG') else None
        }), 500


def register_main_routes(app):

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/kmz')
    def kmz_module():
        return render_template('kmz_module.html')

    @app.route('/rf')
    def rf_module():
        return render_template('rf_module.html')

    @app.route('/health')
    def health_check():
        return jsonify({
            'success': True,
            'status': 'healthy',
            'service': 'rf_tower_system',
            'version': '1.0.0'
        }), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
else:
    application = create_app(os.environ.get('FLASK_ENV', 'production'))
