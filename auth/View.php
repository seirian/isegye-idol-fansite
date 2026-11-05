<?php
declare(strict_types=1);
namespace Isegye\Access;
final class View
{
    public static function e(string $text): string { return htmlspecialchars($text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
    public static function page(string $title, string $content, string $extra = '', string $layout = '', bool $legalLinks = true, string $legalBase = '/auth/'): string
    {
        if (!in_array($legalBase, ['/auth/', '/account/'], true)) throw new \RuntimeException('Invalid legal base');
        $footer = '비공식 팬사이트' . ($legalLinks ? ' · <a href="' . $legalBase . 'terms">이용약관</a> · <a href="' . $legalBase . 'privacy"><strong>개인정보처리방침</strong></a>' : '');
        return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            . '<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="strict-origin-when-cross-origin">'
            . '<title>' . self::e($title) . ' · ISEGYE!</title><link rel="stylesheet" href="/auth/style.css">' . $extra
            . '</head><body class="access-page ' . self::e($layout) . '"><div class="access-backdrop" aria-hidden="true"></div>'
            . '<header class="access-brand"><a href="/">ISEGYE<span>!</span></a><span>이세계아이돌 비공식 팬사이트</span></header>'
            . '<main class="access-main">' . $content . '</main><footer class="access-footer">' . $footer . '</footer></body></html>';
    }
    public static function maintenance(bool $signedIn = false): string
    {
        return self::page('공사중', '<section class="access-card maintenance"><div class="access-mark" aria-hidden="true">✦</div>'
            . '<p class="access-kicker">조금 더 좋은 모습으로 만나요</p><h1>현재 사이트는 <br>공사중입니다.</h1>'
            . '<p class="access-description">이세계아이돌의 소식을 더 편하게 만날 수 있도록<br class="wide-only"> 사이트를 준비하고 있어요.</p>'
            . '<div class="access-divider" aria-hidden="true"><span></span>✦<span></span></div>'
            . '<a class="access-small-link" href="/auth/login">' . ($signedIn ? '로그인 상태 · 계정 관리' : 'Google 로그인') . '</a></section>', '', '', true, '/auth/');
    }
    public static function login(string $clientId, string $nonce, string $csrf): string
    {
        $attrs = ' data-client-id="' . self::e($clientId) . '" data-nonce="' . self::e($nonce) . '" data-csrf="' . self::e($csrf) . '"';
        return self::page('Google 로그인', '<section class="access-card"><p class="access-kicker">다시 만나서 반가워요</p><h1>Google 로그인</h1>'
            . '<p class="access-description">가입 양식 없이 Google 계정으로 시작하세요.<br>처음 로그인하면 회원으로 자동 등록됩니다.</p>'
            . '<p class="access-note access-legal-notice">회원가입은 만 14세 이상을 대상으로 합니다. 계속하면 <a href="/auth/terms">이용약관</a>에 동의하고 <a href="/auth/privacy">개인정보처리방침</a>을 확인한 후 Google 계정으로 시작합니다. 별도 동의가 필요한 개인정보 처리까지 포괄적으로 동의하는 것은 아닙니다.</p>'
            . '<div id="google-signin"' . $attrs . '><p class="access-description" id="signin-loading">로그인 버튼을 불러오는 중입니다.</p><div id="google-button"></div></div>'
            . '<p id="signin-error" class="access-error" role="alert" hidden></p>'
            . '<p class="access-note">이름·이메일·프로필 사진은 저장하지 않습니다.<br>로그인 확인용 식별값과 권한만 보관합니다.</p>'
            . '<a class="access-small-link" href="/">사이트로 돌아가기</a></section>',
            '<script src="https://accounts.google.com/gsi/client" defer></script><script src="/auth/google-client.js" defer></script>');
    }
    public static function account(string $role, string $csrf): string
    {
        return self::page('로그인 상태', '<section class="access-card"><p class="access-kicker">로그인되었습니다</p><h1>'
            . ($role === 'admin' ? '관리자 계정' : '일반회원 계정') . '</h1><p class="access-description">Google 로그인으로 인증된 계정입니다.</p>'
            . '<a class="access-button" href="/">사이트로 돌아가기</a><form method="post" action="/auth/logout">'
            . '<input type="hidden" name="csrf" value="' . self::e($csrf) . '"><button class="access-secondary" type="submit">로그아웃</button></form></section>', '', '', true, '/account/');
    }
    public static function document(string $kind): string
    {
        if (!in_array($kind, ['terms', 'privacy'], true)) throw new \RuntimeException('Unknown legal document');
        $file = __DIR__ . '/' . $kind . '.html';
        if (!is_file($file) || is_link($file)) throw new \RuntimeException('Legal document unavailable');
        $title = $kind === 'terms' ? '서비스 이용약관' : '개인정보처리방침';
        $tabs = '<nav class="legal-tabs" aria-label="이용 안내 문서">';
        foreach (['terms'=>'이용약관','privacy'=>'개인정보처리방침'] as $id=>$label) {
            $tabs .= '<a href="/auth/' . $id . '"' . ($id === $kind ? ' aria-current="page"' : '') . '>' . $label . '</a>';
        }
        $tabs .= '</nav>';
        // Standalone public notices: no application menus, fan guide or about links.
        // A maintenance visitor uses this presentation even with a member session.
        return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            . '<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="strict-origin-when-cross-origin">'
            . '<title>' . self::e($title) . ' · ISEGYE! 이용 안내</title><link rel="stylesheet" href="/auth/legal.css">'
            . '</head><body class="legal-page legal-public legal-standalone"><div class="legal-public-layout">'
            . '<header class="legal-standalone-header"><p>ISEGYE! <span>이용 안내</span></p>'
            . '<fieldset class="legal-public-theme"><legend>화면 테마</legend><label><input type="radio" name="legal-theme" value="auto" checked>자동</label><label><input type="radio" name="legal-theme" value="light">라이트</label><label><input type="radio" name="legal-theme" value="dark">다크</label></fieldset></header>'
            . '<main id="main"><div class="legal-shell" id="document-top"><div class="legal-navigation"><a href="/">← 안내 화면으로</a></div>'
            . $tabs . '<article class="legal-document" data-policy="' . $kind . '" data-version="1.0">' . file_get_contents($file) . '</article></div></main>'
            . '<footer class="legal-standalone-footer"><span>이세계아이돌 비공식 팬사이트 · 이용 안내</span><nav aria-label="이용 안내"><a href="/auth/terms">이용약관</a><a href="/auth/privacy"><strong>개인정보처리방침</strong></a></nav></footer></div></body></html>';
    }
    public static function privacy(): string { return self::document('privacy'); }
    public static function terms(): string { return self::document('terms'); }
}
