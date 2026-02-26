import os
import torch
import torchaudio.transforms as T
import soundfile as sf
from torch.utils.data import Dataset


class EmotionDataset(Dataset):
    def __init__(self, root_dir):
        self.files = []
        self.labels = []

        self.sample_rate = 16000
        self.max_length = 3 * self.sample_rate

        self.label_map = {
            "01": 0,
            "02": 1,
            "03": 2,
            "04": 3,
            "05": 4,
            "06": 5,
            "07": 6,
            "08": 7
        }

        for root, _, filenames in os.walk(root_dir):
            for file in filenames:
                if file.endswith(".wav"):
                    parts = file.split("-")
                    if len(parts) > 2 and parts[2] in self.label_map:
                        self.files.append(os.path.join(root, file))
                        self.labels.append(self.label_map[parts[2]])

        self.mfcc = T.MFCC(
            sample_rate=self.sample_rate,
            n_mfcc=40,
            melkwargs={
                "n_fft": 1024,
                "hop_length": 512,
                "n_mels": 64
            }
        )

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):

        waveform, sr = sf.read(self.files[idx])
        waveform = torch.tensor(waveform).float()

        if len(waveform.shape) > 1:
            waveform = waveform.mean(dim=1)

        waveform = waveform.unsqueeze(0)

        if sr != self.sample_rate:
            resampler = T.Resample(sr, self.sample_rate)
            waveform = resampler(waveform)

        if waveform.shape[1] > self.max_length:
            waveform = waveform[:, :self.max_length]
        else:
            pad = self.max_length - waveform.shape[1]
            waveform = torch.nn.functional.pad(waveform, (0, pad))

        mfcc = self.mfcc(waveform)

        MAX_LEN = 94
        if mfcc.shape[2] > MAX_LEN:
            mfcc = mfcc[:, :, :MAX_LEN]
        else:
            pad_size = MAX_LEN - mfcc.shape[2]
            mfcc = torch.nn.functional.pad(mfcc, (0, pad_size))

        return mfcc, torch.tensor(self.labels[idx])