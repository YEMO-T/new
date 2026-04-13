import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { LogIn, UserPlus, X, Eye, EyeOff, Mail, Lock, User, CheckCircle2, AlertCircle, ArrowRight, Sparkles } from 'lucide-react';
import { cn } from '../../lib/utils';
import { loginUser, registerUser } from '../../services/api';
import { UserInfo } from '../../types';

interface LoginViewProps {
  onLogin: (userInfo: UserInfo) => void;
}

const PulseLoader = ({ className }: { className?: string }) => (
  <div className={cn("flex gap-1 items-center", className)}>
    {[0, 1, 2].map((i) => (
      <motion.div
        key={i}
        className="w-1.5 h-1.5 bg-current rounded-full"
        animate={{
          scale: [1, 1.5, 1],
          opacity: [0.3, 1, 0.3],
        }}
        transition={{
          duration: 1,
          repeat: Infinity,
          delay: i * 0.2,
          ease: "easeInOut",
        }}
      />
    ))}
  </div>
);

export const LoginView = ({ onLogin }: LoginViewProps) => {
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleFieldChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errorMessage) setErrorMessage('');
  };

  const validateForm = () => {
    if (!formData.email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
      setErrorMessage('请输入有效的邮箱地址');
      return false;
    }
    if (formData.password.length < 6) {
      setErrorMessage('密码长度至少需要 6 位');
      return false;
    }
    if (!isLogin && formData.password !== formData.confirmPassword) {
      setErrorMessage('两次输入的密码不一致');
      return false;
    }
    if (!isLogin && !formData.username.trim()) {
      setErrorMessage('请填写用户名');
      return false;
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setIsLoading(true);
    setErrorMessage('');

    try {
      let result;
      if (isLogin) {
        result = await loginUser(formData.email, formData.password);
      } else {
        result = await registerUser(formData.username, formData.email, formData.password);
      }
      localStorage.setItem('auth_token', result.token);
      localStorage.setItem('user_info', JSON.stringify(result.user));
      onLogin(result.user);
    } catch (error: any) {
      setErrorMessage(error.message || (isLogin ? '登录失败，请检查账号密码' : '注册失败，请稍后重试'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[300] bg-[#f0f4f0] flex items-center justify-center overflow-hidden font-['Noto_Sans_SC',_sans-serif]">
      {/* 动态极光背景 */}
      <div className="absolute inset-0 z-0">
        <motion.div 
          animate={{
            scale: [1, 1.2, 1],
            x: [0, 50, 0],
            y: [0, -30, 0],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute -top-[20%] -left-[10%] w-[70%] aspect-square bg-[#0d631b]/5 rounded-full blur-[120px]"
        />
        <motion.div 
          animate={{
            scale: [1.2, 1, 1.2],
            x: [0, -60, 0],
            y: [0, 40, 0],
          }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
          className="absolute -bottom-[10%] -right-[10%] w-[60%] aspect-square bg-[#a3f69c]/10 rounded-full blur-[100px]"
        />
      </div>

      <div className="relative z-10 w-full max-w-[1100px] h-[720px] flex bg-white/40 backdrop-blur-2xl rounded-[48px] border border-white/20 shadow-[0_32px_128px_-16px_rgba(13,99,27,0.12)] overflow-hidden">
        {/* 左侧：表单区 */}
        <div className="flex-1 flex flex-col p-16 overflow-y-auto no-scrollbar">
          <div className="flex items-center gap-4 mb-12">
            <div className="w-12 h-12 rounded-2xl bg-[#0d631b] flex items-center justify-center text-white font-black text-2xl shadow-lg">豆</div>
            <div>
              <h2 className="text-2xl font-black text-[#0d631b] tracking-tight line-height-1">豆沙包</h2>
              <p className="text-[10px] text-[#0d631b]/60 uppercase tracking-[0.2em] font-bold">Smart Teacher Assistant</p>
            </div>
          </div>

          <div className="mb-10">
            <h3 className="text-4xl font-black text-[#161d19] tracking-tight mb-3">
              {isLogin ? "欢迎回来" : "加入我们"}
            </h3>
            <p className="text-[#161d19]/40 font-medium">开启 AI 驱动的高效数字教研之旅</p>
          </div>

          <div className="flex gap-8 mb-10 border-b border-black/5">
            <button 
              onClick={() => { setIsLogin(true); setErrorMessage(''); }}
              className={cn("pb-4 text-sm font-bold transition-all relative", isLogin ? "text-[#0d631b]" : "text-[#161d19]/30")}
            >
              密码登录
              {isLogin && <motion.div layoutId="auth-active" className="absolute bottom-0 left-0 right-0 h-1 bg-[#0d631b] rounded-full" />}
            </button>
            <button 
              onClick={() => { setIsLogin(false); setErrorMessage(''); }}
              className={cn("pb-4 text-sm font-bold transition-all relative", !isLogin ? "text-[#0d631b]" : "text-[#161d19]/30")}
            >
              创建教师账号
              {!isLogin && <motion.div layoutId="auth-active" className="absolute bottom-0 left-0 right-0 h-1 bg-[#0d631b] rounded-full" />}
            </button>
          </div>

          <div className="space-y-6">
            <AnimatePresence mode="wait">
              <motion.div
                key={isLogin ? 'login' : 'register'}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-6"
              >
                {!isLogin && (
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-[#161d19]/60 uppercase tracking-wider ml-1">用户名</label>
                    <div className="relative group">
                      <User className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-[#161d19]/20 group-focus-within:text-[#0d631b] transition-colors" />
                      <input 
                        type="text"
                        value={formData.username}
                        onChange={e => handleFieldChange('username', e.target.value)}
                        className="w-full bg-white/50 border border-black/5 rounded-[20px] pl-14 pr-6 py-4 text-sm focus:ring-4 focus:ring-[#0d631b]/5 focus:border-[#0d631b] transition-all outline-none placeholder-[#161d19]/20"
                        placeholder="如：王老师"
                      />
                    </div>
                  </div>
                )}
                <div className="space-y-2">
                  <label className="text-xs font-bold text-[#161d19]/60 uppercase tracking-wider ml-1">邮箱地址</label>
                  <div className="relative group">
                    <Mail className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-[#161d19]/20 group-focus-within:text-[#0d631b] transition-colors" />
                    <input 
                      type="email"
                      value={formData.email}
                      onChange={e => handleFieldChange('email', e.target.value)}
                      className="w-full bg-white/50 border border-black/5 rounded-[20px] pl-14 pr-6 py-4 text-sm focus:ring-4 focus:ring-[#0d631b]/5 focus:border-[#0d631b] transition-all outline-none placeholder-[#161d19]/20"
                      placeholder="teacher@example.com"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-[#161d19]/60 uppercase tracking-wider ml-1">登录密码</label>
                  <div className="relative group">
                    <Lock className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-[#161d19]/20 group-focus-within:text-[#0d631b] transition-colors" />
                    <input 
                      type={showPassword ? "text" : "password"}
                      value={formData.password}
                      onChange={e => handleFieldChange('password', e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                      className="w-full bg-white/50 border border-black/5 rounded-[20px] pl-14 pr-14 py-4 text-sm focus:ring-4 focus:ring-[#0d631b]/5 focus:border-[#0d631b] transition-all outline-none placeholder-[#161d19]/20"
                      placeholder="至少 6 位密码"
                    />
                    <button 
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-5 top-1/2 -translate-y-1/2 p-1 text-[#161d19]/20 hover:text-[#0d631b] transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>
                {!isLogin && (
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-[#161d19]/60 uppercase tracking-wider ml-1">确认密码</label>
                    <div className="relative group">
                      <CheckCircle2 className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-[#161d19]/20 group-focus-within:text-[#0d631b] transition-colors" />
                      <input 
                        type="password"
                        value={formData.confirmPassword}
                        onChange={e => handleFieldChange('confirmPassword', e.target.value)}
                        className="w-full bg-white/50 border border-black/5 rounded-[20px] pl-14 pr-6 py-4 text-sm focus:ring-4 focus:ring-[#0d631b]/5 focus:border-[#0d631b] transition-all outline-none placeholder-[#161d19]/20"
                        placeholder="请再次输入密码"
                      />
                    </div>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>

            {errorMessage && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-2 p-4 bg-red-50 text-red-600 rounded-2xl text-xs font-bold border border-red-100"
              >
                <AlertCircle className="w-4 h-4" />
                {errorMessage}
              </motion.div>
            )}

            <div className="pt-4 space-y-4">
              <button 
                onClick={handleSubmit}
                disabled={isLoading}
                className="w-full bg-[#0d631b] text-white py-5 rounded-[24px] font-black text-lg shadow-[0_12px_24px_-8px_rgba(13,99,27,0.4)] hover:shadow-[0_16px_32px_-8px_rgba(13,99,27,0.6)] hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-3 disabled:opacity-60"
              >
                {isLoading ? (
                  <>
                    <PulseLoader className="text-white" />
                    <span>正在同步中...</span>
                  </>
                ) : (
                  <>
                    <span>{isLogin ? '安全登录' : '立即加入'}</span>
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>
              
              {isLogin && (
                <div className="flex items-center justify-between px-2 text-[11px] font-bold text-[#161d19]/30 uppercase tracking-wider">
                  <label className="flex items-center gap-2 cursor-pointer hover:text-[#0d631b] transition-colors">
                    <input type="checkbox" className="rounded-sm border-black/10 text-[#0d631b] focus:ring-[#0d631b]" />
                    保持登录状态
                  </label>
                  <button className="hover:text-[#0d631b] transition-colors">忘记密码？</button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 右侧：展示区 */}
        <div className="hidden lg:flex w-[460px] bg-[#0d631b] relative flex-col justify-end p-16 overflow-hidden">
          {/* 背景几何元素 */}
          <div className="absolute top-0 right-0 w-full h-full opacity-10 pointer-events-none">
            <div className="absolute top-[10%] right-[-10%] w-64 h-64 border-[40px] border-white rounded-full"></div>
            <div className="absolute bottom-[20%] left-[-20%] w-96 h-96 border-[60px] border-white rounded-[100px] rotate-45"></div>
          </div>
          
          <div className="relative z-10 text-white">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-md px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest mb-8 border border-white/10">
                <Sparkles className="w-3 h-3 text-[#a3f69c]" />
                <span>Next-Gen Education Tool</span>
              </div>
              <h1 className="text-6xl font-black tracking-tighter mb-8 leading-[0.9]">
                赋能每一位<br /><span className="text-[#a3f69c]">教育者</span>
              </h1>
              <p className="text-lg font-medium text-white/60 leading-relaxed mb-12">
                豆沙包不仅仅是一个助手，它是您的教研合伙人。通过 AI 深度学习您的教学风格，将繁琐的排版与搜素转化为指尖的自然对话。
              </p>
            </motion.div>

            <div className="grid grid-cols-2 gap-10 border-t border-white/10 pt-10">
              <div>
                <p className="text-4xl font-black mb-1">10k+</p>
                <p className="text-[10px] font-bold text-white/30 uppercase tracking-widest">活跃名师</p>
              </div>
              <div>
                <p className="text-4xl font-black mb-1">98%</p>
                <p className="text-[10px] font-bold text-white/30 uppercase tracking-widest">排版提效</p>
              </div>
            </div>
          </div>

          <div className="absolute bottom-[-10%] right-[-10%] w-64 h-64 bg-gradient-to-br from-[#a3f69c]/20 to-transparent rounded-full blur-3xl"></div>
        </div>
      </div>
    </div>
  );
};
