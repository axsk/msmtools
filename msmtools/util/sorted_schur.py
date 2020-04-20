import numpy as np
from scipy.linalg import schur

def top_eigenvalues(P, m, z='LM'):
    """
    Sort the `m+1` dominant eigenvalues up and check, if clustering into 
    `m` clusters would split a complex conjugated pair of eigenvalues.
    
    Parameters
    ----------
    P : ndarray (n,n)
        Transition matrix (row-stochastic).
        
    m : int
        Number of clusters to group into.
        
    z : string, (default='LM')
        Specifies which portion of the spectrum is to be sought.
        The subspace returned will be associated with this part of the spectrum.
        Options are:
        'LM': the m eigenvalues with the largest magnitude are sorted up.
        'LR': the m eigenvalues with the largest real part are sorted up.
        
    """
    
    from scipy.sparse.linalg import eigs 
    
    n = np.shape(P)[0]
    
    if ((m + 1) < (n - 1)):
        top_eigenvals, _ = eigs(P, k=m+1, which=z)
        if np.any(np.isnan(top_eigenvals)):
            raise ValueError("Some of the top m eigenvalues of P are NaN!")
    else: 
        eigenvals = np.linalg.eigvals(P)
        if np.any(np.isnan(eigenvals)):
            raise ValueError("Some eigenvalues of P are NaN!")
        if (z == 'LM'):
            idx = np.argsort(np.abs(eigenvals))
            sorted_eigenvals = eigenvals[idx]
            top_eigenvals = sorted_eigenvals[::-1][:m+1]
        elif (z == 'LR'):
            sorted_eigenvals = np.sort(np.linalg.eigvals(P))
            top_eigenvals = sorted_eigenvals[::-1][:m+1]
    eigenval_in = top_eigenvals[m-1]
    eigenval_out = top_eigenvals[m]
    
    # Don't separate conjugate eigenvalues (corresponding to 2x2-block in R).
    if np.isclose(eigenval_in, eigenval_out):
        raise ValueError("Clustering into " + str(m) " clusters will split conjugate eigenvalues! "
                         + " Request one cluster more or less.")
        
    return top_eigenvals


def sorted_scipy_schur(P, m, z='LM'):
    """
    Perform a full Schur decomposition of `P` while sorting up `m`
    dominant eigenvalues (and associated Schur vectors) at the same time.
    
    Parameters
    ----------
    P : ndarray (n,n)
        Transition matrix (row-stochastic).
        
    m : int
        Number of clusters to group into.
        
    z : string, (default='LM')
        Specifies which portion of the spectrum is to be sought.
        The subspace returned will be associated with this part of the spectrum.
        Options are:
        'LM': the m eigenvalues with the largest magnitude are sorted up.
        'LR': the m eigenvalues with the largest real part are sorted up.
        
    """
    top_eigenvals = top_eigenvalues(P, m, z=z)
    
    eigenval_in = top_eigenvals[m-1]
    eigenval_out = top_eigenvals[m]
        
    if z == 'LM':
        # Determine the cutoff for sorting in schur().
        cutoff = (np.abs(eigenval_in) + np.abs(eigenval_out)) / 2.0 

        R, Q, sdim = schur(P, sort=lambda x: np.abs(x) > cutoff)
    elif z == 'LR':
        # Determine the cutoff for sorting in schur().
        cutoff = (np.real(eigenval_in) + np.real(eigenval_out)) / 2.0 

        R, Q, sdim = schur(P, sort=lambda x: np.real(x) > cutoff)
    
    # Check, if m eigenvalues were really sorted up.
    if not (sdim == m):
        raise ValueError(str(m) + " dominant eigenvalues (associated with the "
                         + "same amount of clusters) were requested, but only " 
                         + str(sdim) + " were sorted up in the Schur form!")
    return (R, Q)


def sorted_krylov_schur(P, m, z='LM'):
    """
    Calculate an orthonormal basis of the subspace associated with the `m`
    dominant eigenvalues of `P` using the Krylov-Schur method as implemented
    in SLEPc.
    
    Parameters
    ----------
    P : ndarray (n,n)
        Transition matrix (row-stochastic).
        
    m : int
        Number of clusters to group into.
        
    z : string, (default='LM')
        Specifies which portion of the spectrum is to be sought.
        The subspace returned will be associated with this part of the spectrum.
        Options are:
        'LM': Largest magnitude (default).
        'LR': Largest real parts.
        
    """
    try:
        from petsc4py import PETSc
        from slepc4py import SLEPc 
    except ImportError as err:
        raise ImportError("Couldn't import SELPc and PETSc: Can't use Krylov-Schur method "
                          + "to construct a sorted partial Schur vector matrix." + err) 
        
    M = PETSc.Mat().create()
    M.createDense(list(np.shape(P)), array=P)
    # Creates EPS object.
    E = SLEPc.EPS().create()
    # Set the matrix associated with the eigenvalue problem.
    E.setOperators(M)
    # Select the particular solver to be used in the EPS object: Krylov-Schur
    E.setType(EPS.Type.KRYLOVSCHUR)
    # Set the number of eigenvalues to compute and the dimension of the subspace.
    E.setDimensions(nev=m)
    # Specify which portion of the spectrum is to be sought. 
    # All possible Options are:
    # (see: https://slepc.upv.es/slepc4py-current/docs/apiref/slepc4py.SLEPc.EPS.Which-class.html)
    # LARGEST_MAGNITUDE: Largest magnitude (default).
    # LARGEST_REAL: Largest real parts.
    # LARGEST_IMAGINARY: Largest imaginary parts in magnitude.
    # SMALLEST_MAGNITUDE: Smallest magnitude.
    # SMALLEST_REAL: Smallest real parts.
    # SMALLEST_IMAGINARY: Smallest imaginary parts in magnitude.
    # TARGET_MAGNITUDE: Closest to target (in magnitude).
    # TARGET_REAL: Real part closest to target.
    # TARGET_IMAGINARY: Imaginary part closest to target.
    # ALL: All eigenvalues in an interval.
    # USER: User defined ordering.
    if z == 'LM':
        E.setWhichEigenpairs(E.Which.LARGEST_MAGNITUDE)
    elif z == 'LR':
        E.setWhichEigenpairs(E.Which.LARGEST_REAL)
    # Solve the eigensystem.
    E.solve()
    # getInvariantSubspace() gets an orthonormal basis of the computed invariant subspace.
    # It returns a list of vectors.
    # The returned vectors span an invariant subspace associated with the computed eigenvalues.
    # OPEN QUESTION: Are we sure that the returned basis vector are always real??
    # WE NEED REAL VECTORS! G-PCCA and PCCA only work with real vectors!!
    # We take the sequence of 1-D arrays and stack them as columns to make a single 2-D array.
    X = np.column_stack([x.array for x in E.getInvariantSubspace()])
    
    # Raise, if X contains complex values!
    if not np.all(np.isreal(X)):
        raise TypeError("The orthonormal basis of the subspace returned by Krylov-Schur is not real!", 
                        "G-PCCA needs real basis vectors to work.")
    
    # The above seems to do the same as scipy.schur with sorting, 
    # but if too many converge the returned space is too big.
    # Cuting the rest off seems to work, but we don't know for sure...
    # So we warn, if this happens.
    if not (np.shape(X)[1] == m):
        warnings.warn("The size of the orthonormal basis of the subspace returned by Krylov-Schur " 
                      + "is to large. The excess is cut off, but it can't be garanteed that this is sane!")
    # Cut off, if too large.
    Q = X[:, :m]
    
    # Gets the number of converged eigenpairs. 
    nconv = E.getConverged()
    # Warn, if nconv smaller than m.
    if not (nconv == m):
        warnings.warn("The number of converged eigenpairs is " + str(nconv) + ", but " + str(m) 
                      + " clusters were requested. They should be the same!")
    # Collect the m dominant eigenvalues.
    top_eigenvalues = []
    top_eigenvalues_error = []
    for i in range(nconv):
        # Get the i-th eigenvalue as computed by solve().
        eigenval = E.getEigenvalue(i)
        top_eigenvalues.append(eigenval)
        # Computes the error (based on the residual norm) associated with the i-th computed eigenpair.
        eigenval_error = E.computeError(i)
        top_eigenvalues_error.append(eigenval_error)
    top_eigenvalues = np.asarray(top_eigenvalues)
    top_eigenvalues_error = np.asarray(top_eigenvalues_error)
    
    return (Q, top_eigenvalues, top_eigenvalues_error)
    

def sorted_schur(P, m, method='brandts'):

    if method == 'brandts':
        # Make a Schur decomposition of P.
        R, Q = schur(P_bar,output='real')
        
        # Sort the Schur matrix and vectors.
        Q, R, ap = sort_real_schur(Q, R, z=np.inf, b=m)
        # Warnings
        if np.any(np.array(ap) > 1.0):
            warnings.warn("Reordering of Schur matrix was inaccurate!")
    elif method == 'scipy':
        R, Q = sorted_scipy_schur(P, m)
    elif method == 'krylov':
        R, Q = sorted_krylov_schur(P, m)
    else:
        raise ValueError("Unknown method" + method)
        
    return (R, Q)
    