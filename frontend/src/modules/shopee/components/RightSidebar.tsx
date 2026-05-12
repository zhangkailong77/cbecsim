interface RightSidebarProps {
  notificationOpen: boolean;
  chatMessagesOpen: boolean;
  onToggleNotification: () => void;
  onToggleChatMessages: () => void;
  notificationCount: number;
}

export default function RightSidebar({ notificationOpen, chatMessagesOpen, onToggleNotification, onToggleChatMessages, notificationCount }: RightSidebarProps) {
  const showBadge = notificationCount > 0;
  const badgeText = notificationCount > 99 ? '99+' : String(notificationCount);
  return (
    <div className="w-[60px] bg-white border-l border-gray-200 h-full flex flex-col items-center py-8 gap-8 flex-shrink-0">
      {/* Notification Bell */}
      <button
        type="button"
        onClick={onToggleNotification}
        className={`relative group cursor-pointer rounded-full transition-colors ${
          notificationOpen ? 'bg-[#fff1ed]' : ''
        }`}
        title={notificationOpen ? '收起通知' : '打开通知'}
      >
        <div
          className={`w-10 h-10 flex items-center justify-center ${
            notificationOpen ? 'text-[#ee4d2d]' : 'text-[#ee4d2d]'
          }`}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" />
          </svg>
        </div>
        {showBadge ? (
          <span className="absolute -top-1 -right-2 bg-[#ee4d2d] text-white text-[10px] font-bold px-1 rounded-full border border-white min-w-[20px] text-center">
            {badgeText}
          </span>
        ) : null}
      </button>

      {/* Customer Service Headset
      <div className="group cursor-pointer">
        <div className="w-10 h-10 flex items-center justify-center text-[#ee4d2d]">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
            <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
            <circle cx="12" cy="12" r="1" fill="currentColor" />
          </svg>
        </div>
      </div> */}

      {/* Chat Messages */}
      <button
        type="button"
        onClick={onToggleChatMessages}
        className={`relative group cursor-pointer rounded-full transition-colors ${
          chatMessagesOpen ? 'bg-[#fff1ed]' : ''
        }`}
        title={chatMessagesOpen ? '收起 Chat Messages' : '打开 Chat Messages'}
      >
        <div className="w-10 h-10 flex items-center justify-center text-[#ee4d2d]">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M11.2167 19.0562C16.0309 19.0562 19.9335 15.4619 19.9335 11.0281C19.9335 6.59431 16.0309 3 11.2167 3C6.40261 3 2.5 6.59431 2.5 11.0281C2.5 13.3008 3.52536 15.3529 5.17326 16.8135L4.64469 19.1019C4.47937 19.8176 5.18393 20.4191 5.84238 20.1243L8.87974 18.7644C9.62348 18.9546 10.4072 19.0562 11.2167 19.0562ZM7.07629 12.3661C7.67805 12.3661 8.16588 11.8669 8.16588 11.2511C8.16588 10.6353 7.67805 10.1361 7.07629 10.1361C6.47452 10.1361 5.98669 10.6353 5.98669 11.2511C5.98669 11.8669 6.47452 12.3661 7.07629 12.3661ZM10.9988 10.1361C11.6006 10.1361 12.0884 10.6353 12.0884 11.2511C12.0884 11.8669 11.6006 12.3661 10.9988 12.3661C10.8332 12.3661 10.6755 12.328 10.535 12.2603C10.1652 12.082 9.90922 11.6972 9.90922 11.2511C9.90922 10.6353 10.3971 10.1361 10.9988 10.1361ZM14.9213 10.1361C15.5231 10.1361 16.0109 10.6353 16.0109 11.2511C16.0109 11.8669 15.5231 12.3661 14.9213 12.3661C14.7558 12.3661 14.5982 12.328 14.4576 12.2604C14.0878 12.0821 13.8318 11.6972 13.8318 11.2511C13.8318 10.6353 14.3196 10.1361 14.9213 10.1361ZM21.0951 11.0278C21.0951 15.2797 18.0653 18.7353 14.0463 19.8587C14.6796 20.0505 15.3563 20.1542 16.0593 20.1542C16.6574 20.1542 17.2365 20.0791 17.7861 19.9386L20.0304 20.9434C20.5169 21.1612 21.0375 20.7168 20.9153 20.1879L20.5248 18.497C21.7424 17.4178 22.5 15.9016 22.5 14.2223C22.5 12.8155 21.9683 11.523 21.0798 10.5062C21.0899 10.6786 21.0951 10.8525 21.0951 11.0278Z"
            />
          </svg>
        </div>
      </button>
    </div>
  );
}
