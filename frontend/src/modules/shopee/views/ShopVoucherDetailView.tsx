import ShopVoucherCreateView from './ShopVoucherCreateView';

interface ShopVoucherDetailViewProps {
  runId: number | null;
  campaignId: number | null;
  onBackToVouchers: () => void;
}

export default function ShopVoucherDetailView({ runId, campaignId, onBackToVouchers }: ShopVoucherDetailViewProps) {
  return (
    <ShopVoucherCreateView
      runId={runId}
      readOnly
      detailCampaignId={campaignId}
      onBackToVouchers={onBackToVouchers}
    />
  );
}
