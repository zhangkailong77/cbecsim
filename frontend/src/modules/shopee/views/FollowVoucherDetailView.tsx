import FollowVoucherCreateView from './FollowVoucherCreateView';

interface FollowVoucherDetailViewProps {
  runId: number | null;
  campaignId: number | null;
  onBackToVouchers: () => void;
}

export default function FollowVoucherDetailView({ runId, campaignId, onBackToVouchers }: FollowVoucherDetailViewProps) {
  return (
    <FollowVoucherCreateView
      runId={runId}
      readOnly
      detailCampaignId={campaignId}
      onBackToVouchers={onBackToVouchers}
    />
  );
}
