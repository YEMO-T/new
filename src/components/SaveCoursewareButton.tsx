import React, { useState } from 'react';
import { SaveAsTemplateModal } from './SaveAsTemplateModal';
import './SaveCoursewareButton.css';

interface SaveCoursewareButtonProps {
  coursewareId: string;
  coursewareTitle?: string;
  onSuccess?: () => void;
  variant?: 'primary' | 'secondary' | 'inline';
  size?: 'small' | 'medium' | 'large';
}

export const SaveCoursewareButton: React.FC<SaveCoursewareButtonProps> = ({
  coursewareId,
  coursewareTitle = '我的课件',
  onSuccess,
  variant = 'secondary',
  size = 'medium'
}) => {
  const [showModal, setShowModal] = useState(false);

  const handleSuccess = () => {
    if (onSuccess) onSuccess();
  };

  return (
    <>
      <button
        className={`save-courseware-btn btn-${variant} btn-${size}`}
        onClick={() => setShowModal(true)}
        title="将当前课件保存为模板，以便后续重复使用"
      >
        <span className="icon">💾</span>
        <span className="label">保存为模板</span>
      </button>

      {showModal && (
        <SaveAsTemplateModal
          coursewareId={coursewareId}
          coursewareTitle={coursewareTitle}
          onClose={() => setShowModal(false)}
          onSuccess={handleSuccess}
        />
      )}
    </>
  );
};

export default SaveCoursewareButton;
