import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest
from argparse import Namespace
import install as i

class InstallTests(unittest.TestCase):
    def test_install_and_refusals(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); bundle=root/'bundle'; source=bundle/'skills/ebonitete'; source.mkdir(parents=True)
            (source/'SKILL.md').write_text('---\nname: ebonitete\n---\nPreflight only')
            import hashlib
            m={'schemaVersion':1,'bundleVersion':'0.1.0','customer':'sivka','repository':'tomih/hodl-client-sivka','runtime':'codex','adapter':'project-standalone-skill','skills':[{'id':'ebonitete','version':'0.1.1','source':'skills/ebonitete','destination':'.agents/skills/ebonitete'}],'files':{'skills/ebonitete/SKILL.md':hashlib.sha256((source/'SKILL.md').read_bytes()).hexdigest()}}
            (bundle/'manifest.json').write_text(json.dumps(m))
            key=root/'test.pub'; key.write_text('ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes(32)).decode())
            receipt={'schemaVersion':1,'type':'hodl.deploy-key.receipt','customer':'sivka','repository':m['repository'],'fingerprint':i.public_key(key)[1],'scope':'read-only','approved':True,'keyId':123}
            rp=root/'receipt.json'; rp.write_text(json.dumps(receipt))
            project=root/'project'; (project/'.hodl').mkdir(parents=True)
            (project/'.hodl/project.json').write_text(json.dumps({'customer':'sivka','repository':m['repository'],'runtime':'codex','project':str(project.resolve())}))
            a=Namespace(bundle=str(bundle),receipt=str(rp),public_key=str(key),project=str(project),customer='sivka',repository=m['repository'])
            for field,value in [('scope','write'),('repository','other/repo'),('fingerprint','SHA256:wrong'),('approved',False)]:
                bad=copy.copy(receipt); bad[field]=value; rp.write_text(json.dumps(bad))
                with self.assertRaises(ValueError): i.install(a)
                self.assertFalse((project/'.agents').exists())
            rp.write_text(json.dumps(receipt))
            (source/'extra').write_text('unexpected')
            with self.assertRaises(ValueError): i.install(a)
            (source/'extra').unlink()
            result=i.install(a); self.assertEqual(result['registration'],'unverified')
            with self.assertRaises(ValueError): i.install(a)
            self.assertFalse((project/'.hodl/install-state.json').exists())
if __name__=='__main__': unittest.main()
