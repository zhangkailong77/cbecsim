import { FormEvent, useEffect, useState } from 'react';
import LoginModal, {
  AuthMode,
  LoginFormState,
  RegisterFormState,
  SchoolOption,
} from './components/LoginModal';
import GameSetupPage, { CreateRunPayload } from './modules/game-setup/GameSetupPage';
import MarketIntelPage from './modules/market-intel/MarketIntelPage';
import LogisticsClearancePage from './modules/logistics-clearance/LogisticsClearancePage';
import WarehouseInboundPage from './modules/warehouse-inbound/WarehouseInboundPage';
import ShopeePage from './modules/shopee/ShopeePage';
import homeLogo from './assets/home/logo.png';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type AppStage = 'loading' | 'setup' | 'intel' | 'logistics' | 'warehouse' | 'shopee';
type RoutedStage = Exclude<AppStage, 'loading'>;
type SetupSubView = 'default' | 'run-data' | 'finance' | 'history' | 'admin-buyer-pool';

function parseStageFromPath(
  pathname: string
): { publicId: string; stage: RoutedStage; setupSubView: SetupSubView } | null {
  const matched = pathname.match(
    /^\/u\/([^/]+)\/(setup|intel|logistics|warehouse|shopee)(?:\/(.*))?\/?$/
  );
  if (!matched) return null;
  const stage = matched[2] as RoutedStage;
  const tail = (matched[3] || '').replace(/^\/+|\/+$/g, '');
  let setupSubView: SetupSubView = 'default';
  if (stage === 'setup') {
    if (tail === 'admin/buyer-pool') setupSubView = 'admin-buyer-pool';
    else if (tail === 'run-data') setupSubView = 'run-data';
    else if (tail === 'finance') setupSubView = 'finance';
    else if (tail === 'history') setupSubView = 'history';
  }
  return {
    publicId: decodeURIComponent(matched[1]),
    stage,
    setupSubView,
  };
}

function buildStagePath(publicId: string, stage: RoutedStage, setupSubView: SetupSubView = 'default'): string {
  if (stage === 'setup' && setupSubView === 'admin-buyer-pool') {
    return `/u/${encodeURIComponent(publicId)}/setup/admin/buyer-pool`;
  }
  if (stage === 'setup' && setupSubView === 'run-data') {
    return `/u/${encodeURIComponent(publicId)}/setup/run-data`;
  }
  if (stage === 'setup' && setupSubView === 'finance') {
    return `/u/${encodeURIComponent(publicId)}/setup/finance`;
  }
  if (stage === 'setup' && setupSubView === 'history') {
    return `/u/${encodeURIComponent(publicId)}/setup/history`;
  }
  return `/u/${encodeURIComponent(publicId)}/${stage}`;
}

interface CurrentRunResponse {
  run: {
    id: number;
    user_id: number;
    initial_cash: number;
    market: string;
    duration_days: number;
    day_index: number;
    status: string;
    created_at: string;
  } | null;
}

interface MeResponse {
  id: number;
  public_id: string;
  username: string;
  role: string;
  full_name: string | null;
  major: string | null;
  class_name: string | null;
  school_name: string | null;
}

export default function App() {
  const [authMode, setAuthMode] = useState<AuthMode>('login');
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAuthChecking, setIsAuthChecking] = useState(false);
  const [appStage, setAppStage] = useState<AppStage>('loading');
  const [currentRun, setCurrentRun] = useState<CurrentRunResponse['run']>(null);
  const [setupError, setSetupError] = useState('');
  const [isStartingRun, setIsStartingRun] = useState(false);
  const [isResettingRun, setIsResettingRun] = useState(false);
  const [currentUser, setCurrentUser] = useState<MeResponse | null>(null);
  const [setupSubView, setSetupSubView] = useState<SetupSubView>('default');
  const [schoolKeyword, setSchoolKeyword] = useState('');
  const [schoolOptions, setSchoolOptions] = useState<SchoolOption[]>([]);
  const [isSchoolLoading, setIsSchoolLoading] = useState(false);
  const [loginForm, setLoginForm] = useState<LoginFormState>({
    username: '',
    password: '',
  });
  const [registerForm, setRegisterForm] = useState<RegisterFormState>({
    school_id: null,
    school_name: '',
    major: '',
    class_name: '',
    full_name: '',
    username: '',
    password: '',
    confirmPassword: '',
  });

  const navigateToStage = (
    stage: RoutedStage,
    options?: { replace?: boolean; setupSubView?: SetupSubView }
  ) => {
    if (!currentUser?.public_id) {
      setAppStage(stage);
      if (stage === 'setup') {
        setSetupSubView(options?.setupSubView ?? 'default');
      } else {
        setSetupSubView('default');
      }
      return;
    }
    const nextSetupSubView = stage === 'setup' ? options?.setupSubView ?? 'default' : 'default';
    const path = buildStagePath(currentUser.public_id, stage, nextSetupSubView);
    if (window.location.pathname !== path) {
      if (options?.replace) {
        window.history.replaceState(null, '', path);
      } else {
        window.history.pushState(null, '', path);
      }
    }
    setAppStage(stage);
    setSetupSubView(nextSetupSubView);
  };

  const resolveStageByCurrentRun = async (token: string, publicId: string) => {
    setSetupError('');
    setAppStage('loading');

    try {
      const response = await fetch(`${API_BASE_URL}/game/runs/current`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        setSetupError('读取开局信息失败，请重试。');
        setCurrentRun(null);
        const fallbackPath = buildStagePath(publicId, 'setup');
        window.history.replaceState(null, '', fallbackPath);
        setAppStage('setup');
        return;
      }

      const data = (await response.json()) as CurrentRunResponse;
      setCurrentRun(data.run);
      const parsed = parseStageFromPath(window.location.pathname);
      const parsedMatched = parsed && parsed.publicId === publicId;
      const stageFromPath = parsedMatched ? parsed.stage : 'setup';
      const setupSubViewFromPath = parsedMatched ? parsed.setupSubView : 'default';
      const canKeepSetupSubView = !data.run && stageFromPath === 'setup';
      const nextStage: RoutedStage = data.run ? stageFromPath : 'setup';
      const nextSetupSubView: SetupSubView =
        nextStage === 'setup' ? (data.run ? setupSubViewFromPath : canKeepSetupSubView ? setupSubViewFromPath : 'default') : 'default';
      const nextPath =
        parsedMatched && (data.run || canKeepSetupSubView)
          ? window.location.pathname
          : buildStagePath(publicId, nextStage, nextSetupSubView);
      window.history.replaceState(null, '', nextPath);
      setAppStage(nextStage);
      setSetupSubView(nextSetupSubView);
    } catch {
      setSetupError('读取开局信息失败，请检查网络后重试。');
      setCurrentRun(null);
      window.history.replaceState(null, '', buildStagePath(publicId, 'setup'));
      setAppStage('setup');
      setSetupSubView('default');
    }
  };

  const fetchMe = async (token: string): Promise<MeResponse | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return null;
      return (await response.json()) as MeResponse;
    } catch {
      return null;
    }
  };

  useEffect(() => {
    const restoreSession = async () => {
      setIsAuthChecking(true);
      const token = localStorage.getItem(ACCESS_TOKEN_KEY);
      if (!token) {
        setIsAuthChecking(false);
        return;
      }

      const me = await fetchMe(token);
      if (!me) {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        setIsAuthenticated(false);
        setCurrentUser(null);
        setIsAuthChecking(false);
        return;
      }

      setCurrentUser(me);
      setIsAuthenticated(true);
      await resolveStageByCurrentRun(token, me.public_id);
      setIsAuthChecking(false);
    };

    void restoreSession();
  }, []);

  useEffect(() => {
    if (authMode !== 'register') return;

    const query = schoolKeyword.trim();
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIsSchoolLoading(true);
      try {
        const params = new URLSearchParams();
        if (query.length > 0) params.set('q', query);
        const response = await fetch(`${API_BASE_URL}/auth/schools?${params.toString()}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          setSchoolOptions([]);
          return;
        }
        const data = (await response.json()) as SchoolOption[];
        setSchoolOptions(data);
      } catch {
        setSchoolOptions([]);
      } finally {
        setIsSchoolLoading(false);
      }
    }, 250);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [authMode, schoolKeyword]);

  useEffect(() => {
    if (!isAuthenticated || !currentUser?.public_id) return;
    const onPopState = () => {
      const parsed = parseStageFromPath(window.location.pathname);
      if (!parsed || parsed.publicId !== currentUser.public_id) {
        window.history.replaceState(null, '', buildStagePath(currentUser.public_id, 'setup'));
        setAppStage('setup');
        setSetupSubView('default');
        return;
      }
      setAppStage(parsed.stage);
      setSetupSubView(parsed.setupSubView);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [isAuthenticated, currentUser?.public_id]);

  const handleLoginSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAuthError('');
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: loginForm.username.trim(),
          password: loginForm.password,
        }),
      });

      if (!response.ok) {
        setAuthError('账号或密码错误，请重试。');
        return;
      }

      const result = await response.json();
      localStorage.setItem(ACCESS_TOKEN_KEY, result.access_token);
      const me = await fetchMe(result.access_token);
      if (!me) {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        setAuthError('读取用户信息失败，请重新登录。');
        return;
      }
      setCurrentUser(me);
      setIsAuthenticated(true);
      setAppStage('loading');
      setLoginForm({ username: '', password: '' });
      await resolveStageByCurrentRun(result.access_token, me.public_id);
    } catch {
      setAuthError('登录服务暂不可用，请稍后再试。');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegisterSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAuthError('');

    if (!registerForm.school_id) {
      setAuthError('请选择学校。');
      return;
    }
    if (!registerForm.major.trim()) {
      setAuthError('请输入专业。');
      return;
    }
    if (!registerForm.class_name.trim()) {
      setAuthError('请输入班级。');
      return;
    }
    if (!registerForm.full_name.trim()) {
      setAuthError('请输入姓名。');
      return;
    }
    if (registerForm.password !== registerForm.confirmPassword) {
      setAuthError('两次输入的密码不一致。');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          school_id: registerForm.school_id,
          major: registerForm.major.trim(),
          class_name: registerForm.class_name.trim(),
          full_name: registerForm.full_name.trim(),
          username: registerForm.username.trim(),
          password: registerForm.password,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        setAuthError(payload.detail || '注册失败，请检查手机号格式或稍后重试。');
        return;
      }

      setRegisterForm({
        school_id: null,
        school_name: '',
        major: '',
        class_name: '',
        full_name: '',
        username: '',
        password: '',
        confirmPassword: '',
      });
      setSchoolKeyword('');
      setSchoolOptions([]);
      setLoginForm({ username: registerForm.username.trim(), password: '' });
      setAuthMode('login');
      setAuthError('注册成功，请使用账号密码登录。');
    } catch {
      setAuthError('注册服务暂不可用，请稍后再试。');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateRun = async (payload: CreateRunPayload) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setSetupError('登录状态失效，请重新登录。');
      setIsAuthenticated(false);
      return;
    }

    setIsStartingRun(true);
    setSetupError('');
    try {
      const response = await fetch(`${API_BASE_URL}/game/runs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (response.status === 201) {
        const created = (await response.json()) as NonNullable<CurrentRunResponse['run']>;
        setCurrentRun(created);
        navigateToStage('intel');
        return;
      }

      if (response.status === 409) {
        if (!currentUser?.public_id) {
          setSetupError('读取用户信息失败，请重新登录。');
          return;
        }
        await resolveStageByCurrentRun(token, currentUser.public_id);
        return;
      }

      const data = await response.json().catch(() => ({}));
      setSetupError(data.detail || '开局创建失败，请稍后重试。');
    } catch {
      setSetupError('开局创建失败，请检查网络后重试。');
    } finally {
      setIsStartingRun(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    setIsAuthenticated(false);
    setCurrentUser(null);
    setAuthMode('login');
    setAppStage('loading');
    window.history.replaceState(null, '', '/');
    setAuthError('');
    setSetupError('');
    setLoginForm({ username: '', password: '' });
  };

  const handleEnterRunningRun = () => {
    navigateToStage('intel');
  };

  const handleEnterLogisticsFromSetup = () => {
    navigateToStage('logistics');
  };

  const handleEnterShopeeFromSetup = () => {
    navigateToStage('shopee');
  };

  const handleEnterShopeeFromIntel = () => {
    navigateToStage('logistics');
  };

  const handleEnterShopeeFromLogistics = () => {
    navigateToStage('warehouse');
  };

  const handleEnterShopeeFromWarehouse = () => {
    navigateToStage('shopee');
  };

  const handleBackToSetupFromIntel = () => {
    navigateToStage('setup');
  };

  const handleBackToSetupFromLogistics = () => {
    navigateToStage('setup');
  };

  const handleBackToSetupFromWarehouse = () => {
    navigateToStage('setup');
  };

  const handleResetCurrentRun = async () => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setSetupError('登录状态失效，请重新登录。');
      setIsAuthenticated(false);
      return;
    }

    setIsResettingRun(true);
    setSetupError('');
    try {
      const response = await fetch(`${API_BASE_URL}/game/runs/reset-current`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setSetupError(data.detail || '重置当前局失败，请稍后重试。');
        return;
      }
      if (!currentUser?.public_id) {
        setSetupError('读取用户信息失败，请重新登录。');
        return;
      }
      await resolveStageByCurrentRun(token, currentUser.public_id);
    } catch {
      setSetupError('重置当前局失败，请检查网络后重试。');
    } finally {
      setIsResettingRun(false);
    }
  };

  let mainContent = <div className="fixed inset-0 bg-[#f5f5f5]" />;
  if (isAuthenticated) {
    if (appStage === 'shopee') {
      mainContent = (
        <ShopeePage
          run={currentRun}
          currentUser={currentUser}
          onBackToSetup={handleBackToSetupFromWarehouse}
        />
      );
    } else if (appStage === 'logistics') {
      mainContent = (
        <LogisticsClearancePage
          run={currentRun}
          currentUser={currentUser}
          onBackToSetup={handleBackToSetupFromLogistics}
          onEnterShopee={handleEnterShopeeFromLogistics}
        />
      );
    } else if (appStage === 'warehouse') {
      mainContent = (
        <WarehouseInboundPage
          run={currentRun}
          currentUser={currentUser}
          onBackToSetup={handleBackToSetupFromWarehouse}
          onEnterShopee={handleEnterShopeeFromWarehouse}
        />
      );
    } else if (appStage === 'intel') {
      mainContent = (
        <MarketIntelPage
          run={currentRun}
          currentUser={currentUser}
          onBackToSetup={handleBackToSetupFromIntel}
          onEnterShopee={handleEnterShopeeFromIntel}
        />
      );
    } else if (appStage === 'setup') {
      mainContent = (
        <GameSetupPage
          isSubmitting={isStartingRun}
          isResetting={isResettingRun}
          error={setupError}
          currentRun={currentRun}
          currentUser={currentUser}
          onSubmit={handleCreateRun}
          onEnterRunningRun={handleEnterRunningRun}
          onEnterLogistics={handleEnterLogisticsFromSetup}
          onEnterWarehouse={() => navigateToStage('warehouse')}
          onEnterShopee={handleEnterShopeeFromSetup}
          onResetCurrentRun={handleResetCurrentRun}
          onLogout={handleLogout}
          setupSubView={setupSubView}
          onSetupSubViewChange={(next) =>
            navigateToStage('setup', { setupSubView: next })
          }
        />
      );
    } else {
      mainContent = (
        <div className="fixed inset-0 flex items-center justify-center bg-[#f5f5f5] text-sm font-semibold text-slate-500">
          正在加载你的经营局...
        </div>
      );
    }
  }

  return (
    <>
      {mainContent}
      {!isAuthChecking && (
        <LoginModal
          open={!isAuthenticated}
          authMode={authMode}
          loginForm={loginForm}
          registerForm={registerForm}
          schoolKeyword={schoolKeyword}
          schoolOptions={schoolOptions}
          isSchoolLoading={isSchoolLoading}
          authError={authError}
          isSubmitting={isSubmitting}
          showPassword={showPassword}
          logoSrc={homeLogo}
          onClose={() => {}}
          onSetAuthMode={setAuthMode}
          onSetLoginForm={setLoginForm}
          onSetRegisterForm={setRegisterForm}
          onSetSchoolKeyword={setSchoolKeyword}
          onSetShowPassword={setShowPassword}
          onClearError={() => setAuthError('')}
          onLoginSubmit={handleLoginSubmit}
          onRegisterSubmit={handleRegisterSubmit}
        />
      )}
    </>
  );
}
