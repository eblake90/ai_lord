import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import skew

# Step 2: Data Generation
np.random.seed(0)  # For reproducibility
sample_size = 1000

# Step 3: Choose a Distribution Model
# Generate data using a log-normal distribution for positive skew
mean = 0
sigma = 1
data = np.random.lognormal(mean, sigma, sample_size)

# Step 5: Visualization
plt.figure(figsize=(10, 6))
plt.hist(data, bins=50, color='blue', alpha=0.7, edgecolor='black')
plt.title('Positively Skewed Distribution (Log-normal)')
plt.xlabel('Value')
plt.ylabel('Frequency')
plt.grid(True)
plt.show()

# Step 6: Analysis and Verification
calculated_skewness = skew(data)
print(f"Calculated Skewness: {calculated_skewness}")

# Step 7: Documentation and Presentation (No code required, handled externally)

# Step 8: Feedback and Iteration (No code required, handled externally)