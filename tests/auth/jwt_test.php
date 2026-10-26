<?php
declare(strict_types=1);
require __DIR__.'/../../auth/vendor/autoload.php';
require_once __DIR__.'/../../auth/GoogleVerifier.php';
use Firebase\JWT\JWT;
use Isegye\Access\GoogleVerifier;
umask(0077);
$dir=sys_get_temp_dir().'/isegye-jwt-test-'.bin2hex(random_bytes(8));mkdir($dir,0700);
$rsa=openssl_pkey_new(['private_key_bits'=>2048,'private_key_type'=>OPENSSL_KEYTYPE_RSA]);
openssl_pkey_export($rsa,$private);
$details=openssl_pkey_get_details($rsa);
$b64=fn($s)=>rtrim(strtr(base64_encode($s),'+/','-_'),'=');
$keys=[['kty'=>'RSA','use'=>'sig','alg'=>'RS256','kid'=>'fixture-key','n'=>$b64($details['rsa']['n']),'e'=>$b64($details['rsa']['e'])]];
file_put_contents($dir.'/google-jwks.json',json_encode(['fetched'=>time(),'expires'=>time()+3600,'keys'=>$keys]));
$client='123456789-fixture.apps.googleusercontent.com';$nonce=str_repeat('a',64);
$base=['iss'=>'https://accounts.google.com','aud'=>$client,'sub'=>'fixture-subject','email'=>'owner.fixture@gmail.com','email_verified'=>true,'iat'=>time(),'exp'=>time()+3600,'nonce'=>$nonce,'name'=>'DO_NOT_STORE','picture'=>'https://example.test/DO_NOT_STORE.png'];
$v=new GoogleVerifier($client,$dir);$checks=[];
function check(string $name,bool $ok):void {global $checks;$checks[]=['name'=>$name,'passed'=>$ok];if(!$ok)throw new RuntimeException($name);}
try{
 $result=$v->verify(JWT::encode($base,$private,'RS256','fixture-key'),$nonce);
 check('valid signature and required claims accepted',$result===['subject'=>'fixture-subject','verifiedEmail'=>'owner.fixture@gmail.com']);
 check('unnecessary profile discarded',!isset($result['name'])&&!isset($result['picture']));
 foreach(['iss'=>'https://evil.test','aud'=>'other.apps.googleusercontent.com','azp'=>'other-client','nonce'=>str_repeat('b',64),'email_verified'=>false,'sub'=>'../bad','email'=>'not-email','exp'=>time()-100,'iat'=>time()+500] as $field=>$value){
  $bad=$base;$bad[$field]=$value;$caught=false;try{$v->verify(JWT::encode($bad,$private,'RS256','fixture-key'),$nonce);}catch(Throwable){$caught=true;}check('reject invalid '.$field,$caught);
 }
 foreach(['iss','aud','sub','email','email_verified','iat','exp','nonce'] as $field){$bad=$base;unset($bad[$field]);$caught=false;try{$v->verify(JWT::encode($bad,$private,'RS256','fixture-key'),$nonce);}catch(Throwable){$caught=true;}check('reject missing '.$field,$caught);}
 $wrong=openssl_pkey_new(['private_key_bits'=>2048,'private_key_type'=>OPENSSL_KEYTYPE_RSA]);openssl_pkey_export($wrong,$wrongPrivate);
 $caught=false;try{$v->verify(JWT::encode($base,$wrongPrivate,'RS256','fixture-key'),$nonce);}catch(Throwable){$caught=true;}check('reject forged signature',$caught);
 $caught=false;try{$v->verify(JWT::encode($base,str_repeat('x',64),'HS256','fixture-key'),$nonce);}catch(Throwable){$caught=true;}check('reject algorithm confusion',$caught);
 foreach(['not-a-jwt',str_repeat('a',17000),'eyJhbGciOiJub25lIn0.eyJzdWIiOiJhIn0.'] as $bad){$caught=false;try{$v->verify($bad,$nonce);}catch(Throwable){$caught=true;}check('reject malformed credential',$caught);}
 @mkdir(__DIR__.'/../../test-results/auth',0755,true);
 file_put_contents(__DIR__.'/../../test-results/auth/jwt.json',json_encode(['scope'=>'synthetic signed fixture JWTs; no real Google login','passed'=>count($checks),'total'=>count($checks),'checks'=>$checks],JSON_PRETTY_PRINT));
 echo json_encode(['passed'=>count($checks),'total'=>count($checks)])."\n";
}finally{foreach(glob($dir.'/*') as $p)unlink($p);rmdir($dir);}
