import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = os.getenv('DEBUG', '0') == '1'
ALLOWED_HOSTS = [x.strip() for x in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if x.strip()]
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if x.strip()]

INSTALLED_APPS = [
    'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions',
    'django.contrib.messages','django.contrib.staticfiles','hub',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,
    'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}
}]
WSGI_APPLICATION='config.wsgi.application'
DATABASES={'default': dj_database_url.config(default=f"sqlite:///{BASE_DIR/'db.sqlite3'}", conn_max_age=600, ssl_require=False)}
AUTH_PASSWORD_VALIDATORS=[
 {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
 {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},
 {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE='en-us'; TIME_ZONE=os.getenv('TIME_ZONE','America/New_York'); USE_I18N=True; USE_TZ=True
STATIC_URL='/static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; STATICFILES_DIRS=[BASE_DIR/'static']
STORAGES={
 'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'},
 'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
}
if os.getenv('AWS_STORAGE_BUCKET_NAME'):
    STORAGES['default']={'BACKEND':'storages.backends.s3boto3.S3Boto3Storage'}
    AWS_ACCESS_KEY_ID=os.getenv('AWS_ACCESS_KEY_ID'); AWS_SECRET_ACCESS_KEY=os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME=os.getenv('AWS_STORAGE_BUCKET_NAME'); AWS_S3_ENDPOINT_URL=os.getenv('AWS_S3_ENDPOINT_URL')
    AWS_S3_REGION_NAME=os.getenv('AWS_S3_REGION_NAME','nyc3'); AWS_DEFAULT_ACL='private'; AWS_QUERYSTRING_AUTH=True
MEDIA_URL='/media/'; MEDIA_ROOT=BASE_DIR/'media'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='login'; LOGIN_REDIRECT_URL='dashboard'; LOGOUT_REDIRECT_URL='login'
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
SESSION_COOKIE_SECURE=not DEBUG; CSRF_COOKIE_SECURE=not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF=True; X_FRAME_OPTIONS='DENY'
APP_ENCRYPTION_KEY=os.getenv('APP_ENCRYPTION_KEY','')

if not DEBUG:
    if SECRET_KEY == 'dev-only-change-me':
        raise RuntimeError('DJANGO_SECRET_KEY must be set in production.')
    if not APP_ENCRYPTION_KEY:
        raise RuntimeError('APP_ENCRYPTION_KEY must be set in production.')
SIGNALHIRE_CALLBACK_BASE_URL=os.getenv('SIGNALHIRE_CALLBACK_BASE_URL','')
