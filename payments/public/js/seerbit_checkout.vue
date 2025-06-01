// This Vue component handles the SeerBit payment checkout process.

<template>
  <div class="seerbit-checkout">
    <div v-if="loading" class="loading-spinner">
      <div class="spinner-border" role="status">
        <span class="sr-only">Loading...</span>
      </div>
      <p>{{ loadingMessage }}</p>
    </div>
    
    <div v-if="error" class="alert alert-danger">
      <h5>Payment Error</h5>
      <p>{{ error }}</p>
      <button @click="retry" class="btn btn-primary">Retry</button>
    </div>
    
    <div v-if="!loading && !error" class="payment-form">
      <h4>Complete Your Payment</h4>
      <div class="payment-summary">
        <p><strong>Amount:</strong> {{ formatCurrency(amount, currency) }}</p>
        <p><strong>Description:</strong> {{ description }}</p>
      </div>
      
      <button 
        @click="initiatePayment" 
        class="btn btn-success btn-lg btn-block"
        :disabled="processing"
      >
        <span v-if="processing">Processing...</span>
        <span v-else>Pay Now with SeerBit</span>
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SeerBitCheckout',
  props: {
    amount: {
      type: Number,
      required: true
    },
    currency: {
      type: String,
      default: 'NGN'
    },
    email: {
      type: String,
      required: true
    },
    fullName: {
      type: String,
      required: true
    },
    mobile: {
      type: String,
      default: ''
    },
    description: {
      type: String,
      default: 'Payment'
    },
    callbackUrl: {
      type: String,
      default: ''
    },
    productId: {
      type: String,
      default: ''
    },
    country: {
      type: String,
      default: 'NG'
    }
  },
  data() {
    return {
      loading: false,
      processing: false,
      error: null,
      loadingMessage: 'Preparing payment...'
    }
  },
  methods: {
    async initiatePayment() {
      this.processing = true;
      this.error = null;
      
      try {
        const paymentData = {
          amount: this.amount,
          currency: this.currency,
          email: this.email,
          full_name: this.fullName,
          mobile: this.mobile,
          callback_url: this.callbackUrl,
          product_id: this.productId,
          product_description: this.description,
          country: this.country
        };
        
        // Call the API to create order
        const response = await this.$call('payments.payment_gateways.seerbit_api.create_seerbit_order', paymentData);
        
        if (response.status === 'success') {
          this.loadingMessage = 'Redirecting to SeerBit...';
          this.loading = true;
          
          // Redirect to SeerBit checkout
          window.location.href = response.redirect_url;
        } else {
          throw new Error(response.message || 'Failed to create payment order');
        }
        
      } catch (error) {
        this.error = error.message;
        this.processing = false;
      }
    },
    
    retry() {
      this.error = null;
      this.processing = false;
      this.loading = false;
    },
    
    formatCurrency(amount, currency) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
      }).format(amount);
    }
  }
}
</script>

<style scoped>
.seerbit-checkout {
  max-width: 500px;
  margin: 0 auto;
  padding: 20px;
}

.loading-spinner {
  text-align: center;
  padding: 40px;
}

.payment-summary {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 5px;
  margin-bottom: 20px;
}

.payment-summary p {
  margin-bottom: 8px;
}

.btn-lg {
  padding: 12px 24px;
  font-size: 18px;
}
</style>