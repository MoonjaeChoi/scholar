#!/usr/bin/env python3
"""
GeForce RTX 5070 12G 최적화 훈련 설정
Generated: 2025-09-27 23:30:00 KST
"""

import os
import paddle

# RTX 5070 12G GPU 최적화 설정
def configure_rtx5070_training():
    """RTX 5070 12G를 위한 최적화 설정"""

    # CUDA 12.4 및 Ada Lovelace 아키텍처 최적화
    os.environ.update({
        # GPU 메모리 관리 (12GB 활용)
        'FLAGS_fraction_of_gpu_memory_to_use': '0.9',  # 10.8GB 사용
        'FLAGS_allocator_strategy': 'auto_growth',
        'FLAGS_enable_cublas_tensor_op_math': 'True',  # Tensor Core 활성화

        # RTX 5070 Ada Lovelace 최적화
        'CUDA_DEVICE_ORDER': 'PCI_BUS_ID',
        'CUDA_VISIBLE_DEVICES': '0',
        'NVIDIA_TF32_OVERRIDE': '1',  # TensorFloat-32 활성화
        'CUDNN_BENCHMARK': '1',  # cuDNN 자동 튜닝

        # 멀티 스레딩 최적화 (Ryzen 5 7500F)
        'OMP_NUM_THREADS': '12',
        'MKL_NUM_THREADS': '12',

        # Mixed Precision 훈련
        'FLAGS_use_pinned_memory': 'True',
        'FLAGS_check_nan_inf': 'False',  # 성능 향상
    })

    # PaddlePaddle GPU 설정
    paddle.device.set_device('gpu:0')

    # GPU 메모리 증분 할당 활성화
    if paddle.device.is_compiled_with_cuda():
        try:
            # RTX 5070 12GB 메모리 최적화
            paddle.device.cuda.set_per_process_memory_fraction(0.9)
            paddle.device.cuda.empty_cache()
            print("✅ RTX 5070 12G GPU 메모리 설정 완료: 10.8GB 할당")
        except Exception as e:
            print(f"⚠️ GPU 메모리 설정 경고: {e}")

    return True

# RTX 5070 최적화 훈련 하이퍼파라미터
RTX5070_TRAINING_CONFIG = {
    # 배치 크기 최적화 (12GB VRAM 기준)
    'detection': {
        'batch_size': 16,  # Detection 모델용
        'learning_rate': 0.001,
        'warmup_steps': 500,
        'max_epochs': 100,
        'save_interval': 10,
        'eval_interval': 5,
        'mixed_precision': True,
        'gradient_accumulation_steps': 2,
    },
    'recognition': {
        'batch_size': 256,  # Recognition 모델용 (작은 이미지)
        'learning_rate': 0.0005,
        'warmup_steps': 300,
        'max_epochs': 150,
        'save_interval': 15,
        'eval_interval': 10,
        'mixed_precision': True,
        'gradient_accumulation_steps': 1,
    },
    'classification': {
        'batch_size': 64,  # 문서 분류용
        'learning_rate': 0.001,
        'warmup_steps': 200,
        'max_epochs': 80,
        'save_interval': 8,
        'eval_interval': 4,
        'mixed_precision': True,
        'gradient_accumulation_steps': 4,
    }
}

# 메모리 최적화 설정
MEMORY_CONFIG = {
    'dataloader_num_workers': 8,  # Ryzen 5 7500F 코어 수 고려
    'prefetch_factor': 4,
    'pin_memory': True,
    'persistent_workers': True,
    'max_queue_size': 32,
}

# RTX 5070 성능 모니터링 설정
MONITORING_CONFIG = {
    'log_gpu_memory': True,
    'log_gpu_utilization': True,
    'profile_steps': 100,
    'tensorboard_log_dir': '/home/pro301/git/en-zine/ocr_system/training_logs/rtx5070',
    'checkpoint_dir': '/opt/models/checkpoints/rtx5070',
}

def get_optimal_batch_size(model_type='detection', available_memory_gb=12):
    """
    RTX 5070 12GB에 최적화된 배치 크기 계산

    Args:
        model_type: 'detection', 'recognition', 'classification'
        available_memory_gb: 사용 가능한 GPU 메모리 (GB)

    Returns:
        최적화된 배치 크기
    """
    base_config = RTX5070_TRAINING_CONFIG.get(model_type, {})
    base_batch_size = base_config.get('batch_size', 8)

    # 메모리 기반 배치 크기 조정
    memory_factor = available_memory_gb / 12.0
    optimal_batch_size = int(base_batch_size * memory_factor)

    # 최소/최대 제한
    if model_type == 'detection':
        optimal_batch_size = max(4, min(32, optimal_batch_size))
    elif model_type == 'recognition':
        optimal_batch_size = max(64, min(512, optimal_batch_size))
    else:  # classification
        optimal_batch_size = max(16, min(128, optimal_batch_size))

    return optimal_batch_size

def setup_mixed_precision_training():
    """Mixed Precision 훈련 설정 (RTX 5070 Tensor Core 활용)"""
    try:
        # AMP (Automatic Mixed Precision) 설정
        from paddle.amp import auto_cast, GradScaler

        # RTX 5070의 4세대 Tensor Core 활용
        scaler = GradScaler(init_loss_scaling=1024.0)

        print("✅ Mixed Precision 훈련 설정 완료 (Tensor Core 활용)")
        return scaler
    except ImportError:
        print("⚠️ Mixed Precision 훈련을 위한 paddle.amp 모듈을 찾을 수 없습니다")
        return None

# 사용 예시
if __name__ == "__main__":
    print("🚀 RTX 5070 12G 최적화 설정 적용 중...")

    # GPU 설정 적용
    success = configure_rtx5070_training()

    if success:
        print("✅ RTX 5070 최적화 설정 완료!")

        # 설정 정보 출력
        for model_type, config in RTX5070_TRAINING_CONFIG.items():
            optimal_batch = get_optimal_batch_size(model_type)
            print(f"📊 {model_type.title()} 모델:")
            print(f"   - 최적 배치 크기: {optimal_batch}")
            print(f"   - Mixed Precision: {config['mixed_precision']}")
            print(f"   - 학습률: {config['learning_rate']}")
    else:
        print("❌ RTX 5070 설정 실패")