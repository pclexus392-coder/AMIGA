"""Production guards and source-only release isolation; no EC2/cloud calls."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from backend.deployment import deployment_errors, create_server
from deploy.ec2.package_release import release_files


class DeploymentTests(unittest.TestCase):
    def values(self):
        return dict(AMIGA_ENV='production', SECRET_KEY='fictional-server-secret-' * 3,
                    DATABASE_URL='postgresql+psycopg://amiga:fictional@127.0.0.1/workspace',
                    PUBLIC_BASE_URL='https://amiga.example.test', AMIGA_ENV_FILE='/etc/amiga/amiga.env',
                    UPLOAD_DIR='/var/lib/amiga/documents', AI_PROVIDER='bedrock', AWS_REGION='us-east-1',
                    BEDROCK_MODEL_ID='us.amazon.nova-lite-v1:0', AGENT_MODEL='gpt-6-luna',
                    OPENAI_API_KEY='fictional-not-a-real-key', ADMIN_BOOTSTRAP_EMAIL='owner@example.test')

    def test_http_sqlite_and_static_keys_are_rejected_before_app_creation(self):
        values=self.values()
        values.update(PUBLIC_BASE_URL='http://203.0.113.1:3000', DATABASE_URL='sqlite:///test.db',
                      AWS_ACCESS_KEY_ID='fictional-aws', AWS_SECRET_ACCESS_KEY='fictional-secret')
        errors=deployment_errors(values)
        for code in ('HTTPS_ENDPOINT_REQUIRED','POSTGRESQL_REQUIRED','EC2_INSTANCE_ROLE_REQUIRED'):
            self.assertIn(code,errors)
        with patch.dict(os.environ,values,clear=True), patch('backend.deployment.Path.is_file',return_value=True), patch('backend.deployment.load_dotenv'), patch('backend.app.create_app') as factory:
            with self.assertRaisesRegex(RuntimeError,'EC2_CONFIGURATION'):create_server()
            factory.assert_not_called()

    def test_production_uses_primary_factory_and_limits_trusted_hosts(self):
        with patch.dict(os.environ,self.values(),clear=True), patch('backend.deployment.Path.is_file',return_value=True), patch('backend.deployment.load_dotenv'), patch('backend.app.create_app',return_value=Mock()) as factory:
            result=create_server()
            self.assertIs(result,factory.return_value)
            self.assertEqual(factory.call_args.args[0]['TRUSTED_HOSTS'],['amiga.example.test','localhost','127.0.0.1'])

    def test_wrong_region_vision_model_and_tls_placeholders_fail_closed(self):
        values=self.values();values.update(AWS_REGION='ap-southeast-1', BEDROCK_MODEL_ID='us.amazon.nova-micro-v1:0', PUBLIC_BASE_URL='https://CHANGE_ME')
        self.assertIn('HTTPS_ENDPOINT_REQUIRED',deployment_errors(values))
        self.assertIn('US_NOVA_LITE_REVIEW_REQUIRED',deployment_errors(values))
        self.assertIn('MENTOR_REGION_REVIEW_REQUIRED',deployment_errors(values))
        values['PUBLIC_BASE_URL']='https://[invalid'
        self.assertIn('HTTPS_ENDPOINT_REQUIRED',deployment_errors(values))

    def test_release_excludes_credentials_documents_and_databases(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'.runtime-temp') as directory:
            root=Path(directory)
            for name in ('backend/app.py','backend/.env','backend/.env.source','backend/.env.example',
                         'backend/storage/client.pdf','backend/storage/data.db','backend/secret.txt',
                         'frontend/portal/index.html','deploy/ec2/.env.example','deploy/ec2/amiga.service'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fictional',encoding='utf-8')
            names={p.relative_to(root).as_posix() for p in release_files(root)}
            self.assertEqual(names,{'backend/app.py','frontend/portal/index.html','deploy/ec2/.env.example','deploy/ec2/amiga.service'})

    def test_only_nginx_binds_the_requested_public_port_80(self):
        import runpy
        root=Path(__file__).resolve().parents[2]
        config=runpy.run_path(str(root/'deploy/ec2/gunicorn.conf.py'))
        self.assertEqual(config['bind'],'127.0.0.1:3000')
        self.assertEqual(config['workers'],1)
        nginx=(root/'deploy/ec2/nginx-amiga.conf').read_text(encoding='utf-8')
        self.assertIn('listen 80;',nginx)
        self.assertIn('proxy_pass http://127.0.0.1:3000;',nginx)
