"""
This file is an example of view the memory allocated by pycuda in a GpuArray
in a CudaNdarray to be able to use it in Theano.

This also serve as a test for the function: cuda_ndarray.from_gpu_pointer
"""

import sys

import numpy

import theano
import theano.sandbox.cuda as cuda_ndarray
import theano.misc.pycuda_init

if not theano.misc.pycuda_init.pycuda_available:
    from nose.plugins.skip import SkipTest
    raise SkipTest("Pycuda not installed. Skip test of theano op with pycuda code.")

if cuda_ndarray.cuda_available == False:
    from nose.plugins.skip import SkipTest
    raise SkipTest('Optional package cuda disabled')

import pycuda
import pycuda.driver as drv
import pycuda.gpuarray


def test_pycuda_simple():
    x = cuda_ndarray.CudaNdarray.zeros((5,5))

    from pycuda.compiler import SourceModule
    mod = SourceModule("""
__global__ void multiply_them(float *dest, float *a, float *b)
{
  const int i = threadIdx.x;
  dest[i] = a[i] * b[i];
}
""")

    multiply_them = mod.get_function("multiply_them")

    a = numpy.random.randn(100).astype(numpy.float32)
    b = numpy.random.randn(100).astype(numpy.float32)

    dest = numpy.zeros_like(a)
    multiply_them(
        drv.Out(dest), drv.In(a), drv.In(b),
        block=(400,1,1), grid=(1,1))
    assert (dest==a*b).all()


def test_pycuda_memory_to_theano():
    #Test that we can use the GpuArray memory space in pycuda in a CudaNdarray
    y = pycuda.gpuarray.zeros((3,4,5), 'float32')
    print numpy.asarray(y)
    print "gpuarray ref count before creating a CudaNdarray", sys.getrefcount(y)
    assert sys.getrefcount(y)==2
    rand = numpy.random.randn(*y.shape).astype(numpy.float32)
    cuda_rand = cuda_ndarray.CudaNdarray(rand)

    strides = [1]
    for i in y.shape[::-1][:-1]:
        strides.append(strides[-1]*i)
    strides = tuple(strides[::-1])
    print 'strides', strides
    assert cuda_rand._strides == strides, (cuda_rand._strides, strides)

    y_ptr = int(y.gpudata) # in pycuda trunk, y.ptr also works, which is a little cleaner
    z = cuda_ndarray.from_gpu_pointer(y_ptr, y.shape, strides, y)
    print "gpuarray ref count after creating a CudaNdarray", sys.getrefcount(y)
    assert sys.getrefcount(y)==3
    assert (numpy.asarray(z) == 0).all()

    cuda_ones = cuda_ndarray.CudaNdarray(numpy.asarray([[[1]]],dtype='float32'))
    z += cuda_ones
    assert (numpy.asarray(z) == numpy.ones(y.shape)).all()
    assert (numpy.asarray(z) == 1).all()

    assert cuda_rand.shape == z.shape
    assert cuda_rand._strides == z._strides, (cuda_rand._strides, z._strides)
    assert (numpy.asarray(cuda_rand) == rand).all()
    z += cuda_rand
    assert (numpy.asarray(z)==(rand+1)).all()

    # Check that the ref count to the gpuarray is right.
    del z
    print "gpuarray ref count after deleting the CudaNdarray", sys.getrefcount(y)
    assert sys.getrefcount(y)==2
