import LiveVoucherCreateView from './LiveVoucherCreateView';

interface LiveVoucherDetailViewProps {
  runId: number | null;
  campaignId: number | null;
  onBackToVouchers: () => void;
}

export default function LiveVoucherDetailView({ runId, campaignId, onBackToVouchers }: LiveVoucherDetailViewProps) {
  return (
    <LiveVoucherCreateView
      runId={runId}
      readOnly
      detailCampaignId={campaignId}
      onBackToVouchers={onBackToVouchers}
    />
  );
}
